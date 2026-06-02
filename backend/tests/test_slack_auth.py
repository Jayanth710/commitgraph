"""Slack request signature verification (the webhook's auth)."""

import hashlib
import hmac
import time

from app.services.slack_auth import verify_slack_signature


def _sign(secret: str, ts: str, body: str) -> str:
    digest = hmac.new(secret.encode(), f"v0:{ts}:{body}".encode(), hashlib.sha256).hexdigest()
    return f"v0={digest}"


def test_valid_signature_passes():
    secret, body, ts = "shh", '{"type":"event_callback"}', str(int(time.time()))
    assert verify_slack_signature(
        signing_secret=secret, timestamp=ts, body=body, signature=_sign(secret, ts, body)
    )


def test_bad_signature_fails():
    ts = str(int(time.time()))
    assert not verify_slack_signature(
        signing_secret="shh", timestamp=ts, body="b", signature="v0=deadbeef"
    )


def test_stale_timestamp_fails():
    secret, body = "shh", "b"
    old = str(int(time.time()) - 10_000)
    assert not verify_slack_signature(
        signing_secret=secret, timestamp=old, body=body, signature=_sign(secret, old, body)
    )


def test_missing_inputs_fail():
    ts = str(int(time.time()))
    assert not verify_slack_signature(signing_secret="", timestamp=ts, body="b", signature="v0=x")
    assert not verify_slack_signature(signing_secret="s", timestamp=None, body="b", signature="v0=x")
    assert not verify_slack_signature(signing_secret="s", timestamp=ts, body="b", signature=None)
