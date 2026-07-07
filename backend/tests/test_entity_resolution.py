"""Entity resolution email/identifier canonicalization."""

from app.services.entity_resolution import (
    canonical_email,
    normalize_gmail_dots,
    strip_plus_tag,
)


def test_slack_identifier_passthrough():
    # Regression: non-email identifiers (no "@") must not crash and pass through.
    assert canonical_email("slack:U0B7K6CEBGS") == "slack:u0b7k6cebgs"


def test_discord_identifier_passthrough():
    assert canonical_email("discord:1234567890") == "discord:1234567890"


def test_gmail_dots_and_plus_tag_normalized():
    assert canonical_email("J.Doe+newsletter@gmail.com") == "jdoe@gmail.com"


def test_strip_plus_tag():
    assert strip_plus_tag("user+promo@work.com") == "user@work.com"


def test_gmail_dots_only_for_gmail():
    assert normalize_gmail_dots("j.d.o.e@gmail.com") == "jdoe@gmail.com"
    assert normalize_gmail_dots("j.doe@work.com") == "j.doe@work.com"
