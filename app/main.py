from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.vk_client import vk, VKAPIError


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await vk.close()


app = FastAPI(title="VK Group Messages", lifespan=lifespan)
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


# ── HTML pages ──────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main page — list of conversations."""
    try:
        conversations = await vk.get_conversations()
    except VKAPIError as e:
        return templates.TemplateResponse("error.html", {
            "request": request, "error": str(e),
        })

    return templates.TemplateResponse("index.html", {
        "request": request,
        "conversations": conversations,
    })


@app.get("/chat/{peer_id}", response_class=HTMLResponse)
async def chat_page(request: Request, peer_id: int):
    """Messages page for a specific conversation."""
    try:
        messages = await vk.get_history(peer_id)
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
async def api_conversations():
    """Return all conversations as JSON."""
    try:
        data = await vk.get_conversations()
        return {"count": len(data), "items": data}
    except VKAPIError as e:
        return JSONResponse({"error": str(e)}, status_code=502)


@app.get("/api/messages/{peer_id}")
async def api_messages(peer_id: int):
    """Return all messages for a conversation as JSON."""
    try:
        messages = await vk.get_history(peer_id)
        return {"count": len(messages), "peer_id": peer_id, "items": messages}
    except VKAPIError as e:
        return JSONResponse({"error": str(e)}, status_code=502)


@app.get("/api/all")
async def api_all():
    """Fetch everything: all conversations + all their messages."""
    try:
        return await vk.get_all_data()
    except VKAPIError as e:
        return JSONResponse({"error": str(e)}, status_code=502)
