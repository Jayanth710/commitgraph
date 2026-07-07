"""
Fixed-window per-IP rate limiting, backed by the existing Redis.

Auth endpoints get a tighter limit (brute-force surface); everything else
gets a generous default. Webhooks and health checks are exempt. Redis errors
fail open so a Redis blip never locks users out.

Implemented with a Lua script so INCR+EXPIRE is atomic and works against both
the local redis client and the Upstash REST adapter (both expose ``eval``).
"""

from __future__ import annotations

import logging
import time

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.services.redis_streams import get_redis_client

settings = get_settings()
logger = logging.getLogger(__name__)

_WINDOW_SECONDS = 60
_EXEMPT_PREFIXES = ("/api/webhooks/", "/health")
_AUTH_PREFIXES = ("/auth/login", "/auth/signup", "/auth/google-login")

# Returns the post-increment counter; sets the TTL only on first hit.
_INCR_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return current
"""


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def rate_limit(request: Request, call_next):
    path = request.url.path
    if path.startswith(_EXEMPT_PREFIXES):
        return await call_next(request)

    is_auth = path.startswith(_AUTH_PREFIXES)
    limit = settings.rate_limit_auth_per_min if is_auth else settings.rate_limit_default_per_min
    scope = "auth" if is_auth else "default"
    window = int(time.time()) // _WINDOW_SECONDS
    key = f"rl:{scope}:{_client_ip(request)}:{window}"

    redis = None
    try:
        redis = get_redis_client()
        count = await redis.eval(_INCR_SCRIPT, 1, key, str(_WINDOW_SECONDS))
    except Exception as exc:
        logger.warning("Rate limiter unavailable, failing open: %s", exc)
        return await call_next(request)
    finally:
        if redis is not None:
            try:
                await redis.aclose()
            except Exception:
                pass

    if count is not None and int(count) > limit:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Please try again shortly."},
        )

    return await call_next(request)
