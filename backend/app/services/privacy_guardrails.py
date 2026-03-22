from __future__ import annotations

import re
from typing import Any

MAX_LLM_SUBJECT_CHARS = 200
MAX_LLM_BODY_CHARS = 1800
MAX_LLM_RECIPIENTS = 10
MAX_FORWARD_UNWRAP_DEPTH = 6

_QUOTED_HISTORY_PATTERNS = [
    re.compile(r"^\s*>"),
    re.compile(r"^\s*On .+ wrote:\s*$", re.IGNORECASE),
    re.compile(r"^\s*From:\s+", re.IGNORECASE),
    re.compile(r"^\s*Sent:\s+", re.IGNORECASE),
    re.compile(r"^\s*To:\s+", re.IGNORECASE),
    re.compile(r"^\s*Cc:\s+", re.IGNORECASE),
    re.compile(r"^\s*Subject:\s+", re.IGNORECASE),
    re.compile(r"^\s*-{2,}\s*Original Message\s*-{2,}\s*$", re.IGNORECASE),
    re.compile(r"^\s*Begin forwarded message:\s*$", re.IGNORECASE),
]
_FORWARDED_MARKERS = [
    re.compile(r"^\s*-{2,}\s*Forwarded message\s*-{2,}\s*$", re.IGNORECASE),
    re.compile(r"^\s*Begin forwarded message:\s*$", re.IGNORECASE),
]
_FORWARDED_HEADER = re.compile(r"^\s*(From|Date|Subject|To|Cc|Bcc):\s+", re.IGNORECASE)

_SIGNATURE_DELIMITER = re.compile(r"^\s*--\s*$")
_SIGNATURE_FOOTERS = [
    re.compile(r"^\s*sent from my (iphone|ipad|android|mobile device)\s*$", re.IGNORECASE),
    re.compile(r"^\s*get outlook for (ios|android)\s*$", re.IGNORECASE),
]
_SIGN_OFF = re.compile(
    r"^\s*(best|thanks|thank you|regards|cheers|sincerely|warmly|respectfully)"
    r"[!,\s]*$",
    re.IGNORECASE,
)
_PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d().\-\s]{7,}\d)(?!\w)")
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_CARDISH = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
_URL = re.compile(r"https?://\S+", re.IGNORECASE)
_ADDRESS_LINE = re.compile(
    r"^\s*\d{1,5}\s+[A-Za-z0-9#.'\- ]+\b"
    r"(street|st|avenue|ave|road|rd|lane|ln|drive|dr|boulevard|blvd|court|ct|circle|cir|way|parkway|pkwy)\b.*$",
    re.IGNORECASE,
)
_TOKENISH = re.compile(r"\b[A-Za-z0-9_\-]{24,}\b")


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text

    trimmed = text[:limit].rsplit(" ", 1)[0].rstrip()
    return f"{trimmed or text[:limit].rstrip()}..."


def _normalize_text(text: str | None) -> str:
    cleaned = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _strip_quoted_history(lines: list[str]) -> list[str]:
    kept: list[str] = []
    for line in lines:
        if any(pattern.match(line) for pattern in _QUOTED_HISTORY_PATTERNS):
            break
        kept.append(line)
    return kept


def _extract_forwarded_payload(lines: list[str], marker_index: int) -> list[str]:
    i = marker_index + 1
    saw_header = False

    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped:
            if saw_header:
                i += 1
                while i < len(lines) and not lines[i].strip():
                    i += 1
                return lines[i:]
            i += 1
            continue

        if _FORWARDED_HEADER.match(lines[i]):
            saw_header = True
            i += 1
            continue

        break

    return lines[marker_index + 1 :]


def _unwrap_forwarded_content(lines: list[str]) -> list[str]:
    current = lines
    for _ in range(MAX_FORWARD_UNWRAP_DEPTH):
        marker_index = next(
            (idx for idx, line in enumerate(current) if any(pattern.match(line) for pattern in _FORWARDED_MARKERS)),
            None,
        )
        if marker_index is None:
            break

        candidate = _extract_forwarded_payload(current, marker_index)
        if candidate == current:
            break
        current = candidate

    return current


def _strip_signature(lines: list[str]) -> list[str]:
    if not lines:
        return lines

    last_nonempty = max((idx for idx, line in enumerate(lines) if line.strip()), default=-1)
    if last_nonempty == -1:
        return lines

    for idx, line in enumerate(lines):
        if _SIGNATURE_DELIMITER.match(line):
            return lines[:idx]

    start = max(1, last_nonempty - 7)
    for idx in range(start, last_nonempty + 1):
        line = lines[idx].strip()
        if not line:
            continue
        if any(pattern.match(line) for pattern in _SIGNATURE_FOOTERS):
            return lines[:idx]
        if _SIGN_OFF.match(line):
            return lines[:idx]

    return lines


def _redact_sensitive_text(text: str) -> str:
    cleaned_lines: list[str] = []
    for line in text.splitlines():
        if _ADDRESS_LINE.match(line):
            cleaned_lines.append("[redacted_address]")
            continue

        redacted_line = _PHONE.sub("[redacted_phone]", line)
        redacted_line = _SSN.sub("[redacted_ssn]", redacted_line)
        redacted_line = _CARDISH.sub("[redacted_account_number]", redacted_line)
        redacted_line = _URL.sub("[redacted_url]", redacted_line)
        redacted_line = _TOKENISH.sub("[redacted_token]", redacted_line)
        cleaned_lines.append(redacted_line)

    redacted = "\n".join(cleaned_lines)
    redacted = re.sub(r"\n{3,}", "\n\n", redacted)
    return redacted.strip()


def sanitize_email_subject(subject: str | None) -> str:
    text = _normalize_text(subject) or "(no subject)"
    text = _redact_sensitive_text(text)
    return _truncate(text, MAX_LLM_SUBJECT_CHARS)


def sanitize_email_body_for_llm(body_text: str | None) -> str:
    normalized = _normalize_text(body_text)
    if not normalized:
        return ""

    lines = _unwrap_forwarded_content(normalized.splitlines())
    latest_only = _strip_quoted_history(lines)
    without_signature = _strip_signature(latest_only)
    text = "\n".join(without_signature).strip() or "\n".join(latest_only).strip()
    text = _redact_sensitive_text(text)
    return _truncate(text, MAX_LLM_BODY_CHARS)


def minimize_recipients_for_llm(recipients: list[dict[str, Any]] | None) -> list[dict[str, str | None]]:
    minimized: list[dict[str, str | None]] = []
    for recipient in recipients or []:
        email = (recipient.get("email") or "").strip().lower()
        recipient_type = (recipient.get("type") or "").strip().lower() or "to"
        if not email:
            continue
        minimized.append({"email": email, "type": recipient_type})
        if len(minimized) >= MAX_LLM_RECIPIENTS:
            break
    return minimized
