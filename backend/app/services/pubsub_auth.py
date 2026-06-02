"""
Authentication for Google Cloud Pub/Sub push webhooks.

When a Pub/Sub push subscription is configured with a service-account identity,
Google attaches a signed OIDC JWT in the ``Authorization: Bearer <token>``
header of every push request. Verifying that token is what stops an attacker
from forging notifications to our webhook endpoint.

We verify:
    1. The signature, against Google's published JWKS (RS256).
    2. The issuer is Google.
    3. The audience matches what was configured on the subscription (if set).
    4. The token's ``email`` is the expected service account and is verified.
"""

from __future__ import annotations

import asyncio
import logging

import jwt
from jwt import InvalidTokenError, PyJWKClient

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"
_GOOGLE_ISSUERS = {"https://accounts.google.com", "accounts.google.com"}

# PyJWKClient caches signing keys in-process, so this does not hit Google on
# every request.
_jwks_client = PyJWKClient(_GOOGLE_CERTS_URL)


class PubSubAuthError(Exception):
    """Raised when a Pub/Sub push token cannot be verified."""


def pubsub_auth_enforced() -> bool:
    """Whether the Gmail webhook must verify the push token.

    Enforced whenever a verification identity is configured, and always in
    production so a misconfiguration fails closed rather than open.
    """
    return bool(settings.pubsub_verification_email) or settings.app_env == "production"


def _verify_sync(token: str) -> dict:
    signing_key = _jwks_client.get_signing_key_from_jwt(token)
    audience = settings.pubsub_audience or None

    claims = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=audience,
        options={"verify_aud": audience is not None},
    )

    if claims.get("iss") not in _GOOGLE_ISSUERS:
        raise PubSubAuthError(f"unexpected issuer: {claims.get('iss')!r}")

    expected_email = settings.pubsub_verification_email
    if expected_email:
        if claims.get("email") != expected_email or not claims.get("email_verified"):
            raise PubSubAuthError("service-account email mismatch or unverified")

    return claims


async def verify_pubsub_token(authorization_header: str | None) -> dict:
    """Verify a Pub/Sub push OIDC token. Raises PubSubAuthError on failure."""
    if not authorization_header or not authorization_header.lower().startswith("bearer "):
        raise PubSubAuthError("missing bearer token")

    token = authorization_header.split(" ", 1)[1].strip()
    try:
        # PyJWKClient uses blocking I/O on a cache miss; keep the event loop free.
        return await asyncio.to_thread(_verify_sync, token)
    except PubSubAuthError:
        raise
    except InvalidTokenError as exc:
        raise PubSubAuthError(f"invalid token: {exc}") from exc
    except Exception as exc:  # network / JWKS errors
        raise PubSubAuthError(f"verification failed: {exc}") from exc
