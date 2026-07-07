"""
CSRF protection via Origin verification.

Because the auth cookie is SameSite=None in production (frontend and backend
are on different domains), the browser will attach it to cross-site requests,
which reopens the door to CSRF. We close it by requiring that state-changing
requests carry an Origin (or Referer) belonging to our own frontend.

Exemptions:
    - Non-mutating methods (GET/HEAD/OPTIONS) — can't change state.
    - Webhook endpoints — called by Google/Microsoft, authenticated separately.
    - Requests bearing an Authorization header — Bearer auth isn't ambient, so
      an attacker site can't forge it cross-origin.
"""

from __future__ import annotations

from urllib.parse import urlparse

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.config import get_settings

settings = get_settings()

_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_EXEMPT_PREFIXES = ("/api/webhooks/",)


def _request_origin(request: Request) -> str | None:
    origin = request.headers.get("origin")
    if origin:
        return origin
    referer = request.headers.get("referer")
    if referer:
        parsed = urlparse(referer)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
    return None


async def csrf_protect(request: Request, call_next):
    path = request.url.path
    if request.method in _MUTATING_METHODS and not path.startswith(_EXEMPT_PREFIXES):
        # Bearer-authenticated (non-browser) clients are not CSRF-able.
        if not request.headers.get("authorization"):
            origin = _request_origin(request)
            if origin not in settings.cors_origins_list:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF check failed: origin not allowed"},
                )
    return await call_next(request)
