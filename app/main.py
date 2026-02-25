import hmac
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import AuthMiddleware, COOKIE_NAME, make_session_token
from app.config import APP_SECRET
from app.vk_client import vk, VKAPIError


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await vk.close()


app = FastAPI(title="VK Group Messages", lifespan=lifespan)
app.add_middleware(AuthMiddleware)
templates = Jinja2Templates(directory="app/templates")


def format_ts(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def get_peer_title(conv_item: dict) -> str:
    """Build a human-readable title for a conversation."""
    conv = conv_item["conversation"]
    peer = conv["peer"]
    peer_type = peer["type"]
    peer_id = peer["id"]

    if peer_type == "chat":
        settings = conv.get("chat_settings", {})
        return settings.get("title", f"Chat {peer_id}")

    if peer_type == "user":
        profiles = conv_item.get("profiles") or conv_item.get("_profiles") or {}
        user = profiles.get(peer_id)
        if user:
            return f"{user['first_name']} {user['last_name']}"
        return f"User {peer_id}"

    if peer_type == "group":
        groups = conv_item.get("groups") or conv_item.get("_groups") or {}
        group = groups.get(peer_id) or groups.get(-peer_id)
        if group:
            return group.get("name", f"Group {peer_id}")
        return f"Group {peer_id}"

    return f"Peer {peer_id}"


templates.env.filters["format_ts"] = format_ts
templates.env.filters["get_peer_title"] = get_peer_title


# ── Auth ────────────────────────────────────────────────────


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    return templates.TemplateResponse("login.html", {
        "request": request, "error": error,
    })


@app.post("/login")
async def login_submit(secret: str = Form(...)):
    if not hmac.compare_digest(secret, APP_SECRET):
        return RedirectResponse(url="/login?error=wrong_key", status_code=302)

    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(
        key=COOKIE_NAME,
        value=make_session_token(),
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,  # 30 days
    )
    return response


@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(COOKIE_NAME)
    return response


# ── HTML pages ──────────────────────────────────────────────


def _parse_date(date_str: str | None) -> int:
    """Parse YYYY-MM-DD to unix timestamp (UTC), or 0 if empty."""
    if not date_str:
        return 0
    return int(datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


def _filter_by_dates(conversations: list[dict], date_from: str | None, date_to: str | None) -> list[dict]:
    """Filter conversations by last_message.date within [date_from, date_to]."""
    if not date_from and not date_to:
        return conversations

    ts_from = _parse_date(date_from)
    ts_to = _parse_date(date_to) + 86399 if date_to else float("inf")

    result = []
    for item in conversations:
        last_msg = item.get("last_message")
        if not last_msg:
            continue
        ts = last_msg.get("date", 0)
        if ts_from <= ts <= ts_to:
            result.append(item)
    return result


@app.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    """Main page — list of conversations with optional date filter."""
    try:
        conversations = await vk.get_conversations(date_from_ts=_parse_date(date_from))
    except VKAPIError as e:
        return templates.TemplateResponse("error.html", {
            "request": request, "error": str(e),
        })

    total_all = len(conversations)
    conversations = _filter_by_dates(conversations, date_from, date_to)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "conversations": conversations,
        "total_all": total_all,
        "date_from": date_from or "",
        "date_to": date_to or "",
    })


@app.get("/chat/{peer_id}", response_class=HTMLResponse)
async def chat_page(request: Request, peer_id: int, msg_limit: int = Query(0, ge=0)):
    """Messages page for a specific conversation."""
    try:
        messages = await vk.get_history(peer_id, limit=msg_limit)
    except VKAPIError as e:
        return templates.TemplateResponse("error.html", {
            "request": request, "error": str(e),
        })

    messages.reverse()  # chronological order

    return templates.TemplateResponse("chat.html", {
        "request": request,
        "peer_id": peer_id,
        "messages": messages,
        "total": len(messages),
    })


# ── JSON API ────────────────────────────────────────────────


@app.get("/api/conversations")
async def api_conversations(
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    """Return all conversations as JSON, optionally filtered by date range."""
    try:
        data = await vk.get_conversations(date_from_ts=_parse_date(date_from))
        data = _filter_by_dates(data, date_from, date_to)
        return {"count": len(data), "items": data}
    except VKAPIError as e:
        return JSONResponse({"error": str(e)}, status_code=502)


@app.get("/api/messages/{peer_id}")
async def api_messages(peer_id: int, msg_limit: int = Query(0, ge=0)):
    """Return all messages for a conversation as JSON."""
    try:
        messages = await vk.get_history(peer_id, limit=msg_limit)
        return {"count": len(messages), "peer_id": peer_id, "items": messages}
    except VKAPIError as e:
        return JSONResponse({"error": str(e)}, status_code=502)


@app.get("/api/all")
async def api_all(
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    msg_limit: int = Query(0, ge=0),
):
    """Fetch everything: all conversations + all their messages, optionally filtered by date range."""
    try:
        data = await vk.get_all_data(date_from_ts=_parse_date(date_from), msg_limit=msg_limit)
        if date_from or date_to:
            data["conversations"] = _filter_by_dates(data["conversations"], date_from, date_to)
            data["total_conversations"] = len(data["conversations"])
        return data
    except VKAPIError as e:
        return JSONResponse({"error": str(e)}, status_code=502)
