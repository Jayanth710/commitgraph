"""Slack markup cleaning + timestamp parsing (chat ingestion helpers)."""

from app.services.slack_ingest import _clean_slack_markup, _slack_ts_to_dt


def test_clean_removes_broadcast_and_user_mention():
    assert _clean_slack_markup("<!channel> hi <@U1|bob>") == "hi @bob"


def test_clean_link_uses_label():
    assert _clean_slack_markup("see <https://x.co|the docs>") == "see the docs"


def test_clean_link_without_label_uses_url():
    assert _clean_slack_markup("<https://x.co/path>") == "https://x.co/path"


def test_clean_channel_mention():
    assert _clean_slack_markup("in <#C1|general>") == "in #general"


def test_clean_empty():
    assert _clean_slack_markup("") == ""
    assert _clean_slack_markup(None) == ""


def test_ts_to_dt_parses():
    dt = _slack_ts_to_dt("1717261923.123456")
    assert dt is not None and dt.year == 2024


def test_ts_to_dt_invalid_returns_none():
    assert _slack_ts_to_dt("not-a-ts") is None
    assert _slack_ts_to_dt(None) is None
