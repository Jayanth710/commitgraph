"""
Slack request signature verification.

Slack signs every Events API request with an HMAC-SHA256 over
``v0:{timestamp}:{raw_body}`` keyed by the app's signing secret, sent in the
``X-Slack-Signature`` header (``v0=<hex>``) alongside
``X-Slack-Request-Timestamp``. Verifying it is what stops an attacker from
forging events to our endpoint. We also reject stale timestamps to blunt replay.
"""

from __future__ import annotations

import hashlib
import hmac
import time

_SIGNATURE_VERSION = "v0"
_MAX_SKEW_SECONDS = 60 * 5  # reject requests older/newer than 5 minutes (replay guard)


def verify_slack_signature(
    *,
    signing_secret: str,
    timestamp: str | None,
    body: str,
    signature: str | None,
    now: float | None = None,
) -> bool:
    """Return True iff the request signature is valid and recent.

    ``body`` must be the exact raw request body (not re-serialized JSON).
    """
    if not signing_secret or not timestamp or not signature:
        return False

    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False

    current = now if now is not None else time.time()
    if abs(current - ts) > _MAX_SKEW_SECONDS:
        return False

    basestring = f"{_SIGNATURE_VERSION}:{timestamp}:{body}".encode()
    digest = hmac.new(signing_secret.encode(), basestring, hashlib.sha256).hexdigest()
    expected = f"{_SIGNATURE_VERSION}={digest}"

    return hmac.compare_digest(expected, signature)
