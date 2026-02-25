import hashlib
import hmac

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse

from app.config import APP_SECRET, COOKIE_SIGN_KEY

COOKIE_NAME = "vk_session"
PUBLIC_PATHS = {"/login", "/logout"}


def _sign(value: str) -> str:
    """Create HMAC signature for a cookie value."""
    return hmac.new(COOKIE_SIGN_KEY.encode(), value.encode(), hashlib.sha256).hexdigest()


def make_session_token() -> str:
    """Create a signed session cookie value."""
    sig = _sign(APP_SECRET)
    return f"{sig}"


def verify_session(token: str) -> bool:
    """Verify that session cookie is valid."""
    expected = _sign(APP_SECRET)
    return hmac.compare_digest(token, expected)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path in PUBLIC_PATHS:
            return await call_next(request)

        # Check cookie
        session = request.cookies.get(COOKIE_NAME)
        if session and verify_session(session):
            return await call_next(request)

        # Check ?key= query param (for API usage)
        key = request.query_params.get("key")
        if key and hmac.compare_digest(key, APP_SECRET):
            return await call_next(request)

        # Not authenticated — redirect to login (HTML) or return 401 (API)
        if path.startswith("/api/"):
            from starlette.responses import JSONResponse
            return JSONResponse({"error": "Unauthorized. Pass ?key=YOUR_APP_SECRET"}, status_code=401)

        return RedirectResponse(url="/login", status_code=302)
