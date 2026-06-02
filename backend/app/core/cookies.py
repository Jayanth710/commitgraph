"""Helpers for setting/clearing the auth JWT as an httpOnly cookie.

Storing the JWT in an httpOnly cookie (instead of localStorage) means page
JavaScript can't read it, so an XSS payload can't exfiltrate the token. The
cookie still rides along on every request to the backend automatically.

Cookie security is derived from the request transport rather than an env flag,
so it can't be silently misconfigured:
  - HTTPS (incl. behind a proxy that sets X-Forwarded-Proto: https, like Cloud
    Run): Secure + SameSite=None, required to send the cookie cross-site
    (Vercel frontend -> Cloud Run backend).
  - Plain HTTP (local dev): SameSite=Lax without Secure, which works for the
    same-site localhost setup.
"""

from __future__ import annotations

from fastapi import Request, Response

from app.core.config import get_settings

settings = get_settings()


def _is_secure_request(request: Request) -> bool:
    """True if the original client connection was HTTPS.

    Honors X-Forwarded-Proto because TLS is terminated at the proxy/load
    balancer (e.g. Cloud Run) and the app itself sees plain HTTP.
    """
    forwarded_proto = request.headers.get("x-forwarded-proto")
    if forwarded_proto:
        return forwarded_proto.split(",")[0].strip().lower() == "https"
    return request.url.scheme == "https"


def set_auth_cookie(request: Request, response: Response, token: str) -> None:
    secure = _is_secure_request(request)
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=settings.jwt_expire_minutes * 60,
        httponly=True,
        secure=secure,
        samesite="none" if secure else "lax",
        path="/",
    )


def clear_auth_cookie(request: Request, response: Response) -> None:
    secure = _is_secure_request(request)
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path="/",
        httponly=True,
        secure=secure,
        samesite="none" if secure else "lax",
    )
