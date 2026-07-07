"""Privacy guardrails: the layer that sanitizes email before it reaches the LLM.

These assert the *important* property (sensitive values are removed; quoted
history / signatures / forward headers are stripped) without over-coupling to
exact redaction labels. The known false-positive (ISO dates eaten by the phone
regex) is captured as an xfail so it's tracked, not forgotten."""

import pytest

from app.services.privacy_guardrails import (
    minimize_recipients_for_llm,
    sanitize_email_body_for_llm,
    sanitize_email_subject,
)


def test_strips_quoted_reply_history():
    body = "Sure, I'll do it.\n\nOn Mon, Bob <bob@x.com> wrote:\n> please do X"
    out = sanitize_email_body_for_llm(body)
    assert "I'll do it" in out
    assert "please do X" not in out
    assert "bob@x.com" not in out


def test_strips_signature():
    body = "Here is the update.\n\nBest,\nJayanth\n123 Main Street"
    out = sanitize_email_body_for_llm(body)
    assert "Here is the update" in out
    assert "Jayanth" not in out


def test_unwraps_forwarded_header_block():
    body = (
        "---------- Forwarded message ---------\n"
        "From: Recruiter <r@firm.com>\n"
        "Date: Mon\n"
        "Subject: Role\n\n"
        "We'd love to schedule a call."
    )
    out = sanitize_email_body_for_llm(body)
    assert "schedule a call" in out
    assert "Forwarded message" not in out


def test_redacts_phone():
    out = sanitize_email_body_for_llm("Call me at 555 123 4567 tomorrow.")
    assert "555 123 4567" not in out
    assert "[redacted_phone]" in out


def test_redacts_ssn_value():
    # The digits must be gone (the label may be [redacted_phone] due to ordering).
    out = sanitize_email_body_for_llm("SSN 123-45-6789 on file.")
    assert "123-45-6789" not in out


def test_redacts_url():
    out = sanitize_email_body_for_llm("See https://secret.example.com/abc here.")
    assert "secret.example.com" not in out
    assert "[redacted_url]" in out


def test_redacts_standalone_street_address_line():
    out = sanitize_email_body_for_llm("Meeting at:\n500 Oak Avenue\nsee you there")
    assert "Oak Avenue" not in out
    assert "[redacted_address]" in out


@pytest.mark.xfail(reason="Known limitation: addresses embedded mid-sentence aren't matched")
def test_redacts_inline_street_address():
    out = sanitize_email_body_for_llm("Ship to 500 Oak Avenue today.")
    assert "Oak Avenue" not in out


def test_truncates_long_body():
    out = sanitize_email_body_for_llm("word " * 1000)
    assert len(out) <= 1804  # MAX_LLM_BODY_CHARS (1800) + ellipsis


def test_minimize_recipients_caps_and_lowercases():
    recipients = [{"email": f"User{i}@X.com", "type": "to"} for i in range(15)]
    out = minimize_recipients_for_llm(recipients)
    assert len(out) == 10  # capped at MAX_LLM_RECIPIENTS
    assert out[0]["email"] == "user0@x.com"


def test_minimize_recipients_defaults_type_and_skips_blank():
    out = minimize_recipients_for_llm([{"email": "a@b.com"}, {"email": ""}])
    assert out == [{"email": "a@b.com", "type": "to"}]


def test_subject_strips_reply_and_forward_prefixes():
    assert sanitize_email_subject("Re: FW: Q3 Proposal").lower().startswith("q3")


def test_subject_empty_becomes_placeholder():
    assert sanitize_email_subject(None) == "(no subject)"


@pytest.mark.xfail(reason="Known bug: ISO dates match the phone regex and get redacted")
def test_iso_date_should_not_be_redacted():
    out = sanitize_email_body_for_llm("Deliver the report by 2026-03-17.")
    assert "2026-03-17" in out
