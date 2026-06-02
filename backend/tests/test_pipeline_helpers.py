"""Extraction pipeline helpers."""

from app.agents.pipeline import _parse_due_date


def test_parse_iso_date():
    dt = _parse_due_date("2026-06-01")
    assert dt is not None
    assert (dt.year, dt.month, dt.day) == (2026, 6, 1)
    assert dt.tzinfo is not None


def test_parse_none():
    assert _parse_due_date(None) is None
    assert _parse_due_date("") is None


def test_parse_invalid():
    assert _parse_due_date("not-a-date") is None
    assert _parse_due_date("2026-13-99") is None
