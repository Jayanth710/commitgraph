from __future__ import annotations

import re
from typing import Any

MAX_LLM_SUBJECT_CHARS = 200
MAX_LLM_BODY_CHARS = 1800
MAX_LLM_RECIPIENTS = 10
MAX_FORWARD_UNWRAP_DEPTH = 6

# Patterns that mark the boundary between the newest message and older quoted
# history (replies). Forward headers (From:/Date:/Subject: at the *top* of a
# body) are handled separately by _unwrap_forwarded_content — the unwrap runs
# first, so if this email IS a forward, the header block is already gone by
# the time we strip quoted history.
_QUOTED_HISTORY_PATTERNS = [
    re.compile(r"^\s*>"),
    re.compile(r"^\s*On .+ wrote:\s*$", re.IGNORECASE),
    re.compile(r"^\s*From:\s+", re.IGNORECASE),
    re.compile(r"^\s*Sent:\s+", re.IGNORECASE),
    re.compile(r"^\s*To:\s+", re.IGNORECASE),
    re.compile(r"^\s*Cc:\s+", re.IGNORECASE),
    re.compile(r"^\s*Subject:\s+", re.IGNORECASE),
    re.compile(r"^\s*-{2,}\s*Original Message\s*-{2,}\s*$", re.IGNORECASE),
    # Mashed single-line header used as a reply quote boundary too
    re.compile(r"^\s*From:\s*[^\n]*?\bSubject:\s*", re.IGNORECASE),
]
_FORWARDED_MARKERS = [
    re.compile(r"^\s*-{2,}\s*Forwarded message\s*-{2,}\s*$", re.IGNORECASE),
    re.compile(r"^\s*Begin forwarded message:\s*$", re.IGNORECASE),
]
_FORWARDED_HEADER = re.compile(r"^\s*(From|Date|Sent|Subject|To|Cc|Bcc|Reply-To):\s+", re.IGNORECASE)

# Matches an Outlook-style "mashed" forward header where From/Date/To/Subject
# are all concatenated on a single line, e.g.:
#   "From: Tesla <noreply@tesla.com> Date: ... To: ... Subject: ..."
_MASHED_FORWARD_HEADER = re.compile(
    r"^\s*From:.*?\bSubject:\s*",
    re.IGNORECASE,
)

# Extracts the original sender's email from a forward header (handles both
# mashed single-line and multi-line variants).
_FROM_ADDRESS_RE = re.compile(
    r"From:\s*[^\n]*?<?([\w.+\-]+@[\w.\-]+)>?",
    re.IGNORECASE,
)

_SIGNATURE_DELIMITER = re.compile(r"^\s*--\s*$")
_SIGNATURE_FOOTERS = [
    re.compile(r"^\s*sent from my (iphone|ipad|android|mobile device)\s*$", re.IGNORECASE),
    re.compile(r"^\s*get outlook for (ios|android|mac)\s*$", re.IGNORECASE),
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

# Noisy lines that some clients/gateways inject and that should be dropped
# from the sanitized output (they carry no signal and can confuse the LLM).
_NOISE_LINES = [
    re.compile(r"^\s*\[external email[^\]]*\]\s*$", re.IGNORECASE),
    re.compile(r"^\s*get outlook for (ios|android|mac)\s*$", re.IGNORECASE),
    re.compile(r"^\s*caution:\s*external email.*$", re.IGNORECASE),
]


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


def _strip_noise_lines(lines: list[str]) -> list[str]:
    return [line for line in lines if not any(p.match(line) for p in _NOISE_LINES)]


def _extract_forwarded_payload(lines: list[str], marker_index: int) -> list[str]:
    """Skip past an explicit forward marker and any header lines that follow it."""
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


def _find_implicit_forward_end(lines: list[str]) -> int | None:
    """Locate an Outlook-style forward header block that has no explicit
    '--- Forwarded message ---' marker, and return the index of the first
    content line after the header block.

    Crucially, this only fires when the header sits at the *top* of the body
    (no substantive content precedes it). If there's real prose above the
    'From:' line, it's a reply-quote marker — not a forward — and the caller
    should use _strip_quoted_history instead.

    Handles two variants of the header at the top:
      1. Mashed single line: "From: X <a@b> Date: Y To: Z Subject: W"
      2. Multi-line block:   "From: ...\\nDate: ...\\nSubject: ...\\n"
    """
    substantive_preamble = 0
    for idx, line in enumerate(lines):
        if not line.strip():
            continue

        # Variant 1: single-line mashed header at top
        if _MASHED_FORWARD_HEADER.match(line):
            if substantive_preamble > 0:
                return None
            end = idx + 1
            while end < len(lines) and not lines[end].strip():
                end += 1
            return end

        # Variant 2: multi-line header block at top
        if _FORWARDED_HEADER.match(line):
            if substantive_preamble > 0:
                return None
            end = idx
            header_count = 0
            while end < len(lines):
                if _FORWARDED_HEADER.match(lines[end]):
                    header_count += 1
                    end += 1
                elif not lines[end].strip():
                    end += 1
                else:
                    break
            if header_count >= 2:
                while end < len(lines) and not lines[end].strip():
                    end += 1
                return end
            # Single stray "From:" — not enough to call it a forward
            return None

        # Any other non-blank line means we have real prose above the header,
        # so the header (when we reach it) will be a reply quote, not a forward.
        substantive_preamble += 1
    return None


def _unwrap_forwarded_content(lines: list[str]) -> list[str]:
    current = lines
    for _ in range(MAX_FORWARD_UNWRAP_DEPTH):
        # Prefer an explicit forward marker if one is present.
        marker_index = next(
            (
                idx
                for idx, line in enumerate(current)
                if any(pattern.match(line) for pattern in _FORWARDED_MARKERS)
            ),
            None,
        )
        if marker_index is not None:
            candidate = _extract_forwarded_payload(current, marker_index)
            if candidate == current:
                break
            current = candidate
            continue

        # Otherwise, try to detect an implicit (Outlook-style) forward header.
        implicit_end = _find_implicit_forward_end(current)
        if implicit_end is not None and 0 < implicit_end < len(current):
            current = current[implicit_end:]
            continue

        break

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
    # Strip "FW:" / "Fwd:" / "RE:" prefixes so the LLM sees the real subject.
    text = re.sub(r"^(?:(?:FW|FWD|RE|AW):\s*)+", "", text, flags=re.IGNORECASE).strip()
    text = _redact_sensitive_text(text)
    return _truncate(text, MAX_LLM_SUBJECT_CHARS)


def sanitize_email_body_for_llm(body_text: str | None) -> str:
    normalized = _normalize_text(body_text)
    if not normalized:
        return ""

    # Order matters here:
    #   1. strip noise banners so they don't count as preamble above forward headers
    #   2. unwrap forwards — drops header block and keeps what follows
    #   3. strip reply quotes — drops everything after an "On X wrote:" / "From:" marker
    #   4. strip signature — drops sign-off and everything after
    lines = _strip_noise_lines(normalized.splitlines())
    lines = _unwrap_forwarded_content(lines)
    latest_only = _strip_quoted_history(lines)
    without_signature = _strip_signature(latest_only)
    text = "\n".join(without_signature).strip() or "\n".join(latest_only).strip()
    text = _redact_sensitive_text(text)
    return _truncate(text, MAX_LLM_BODY_CHARS)


def extract_forwarded_sender(body_text: str | None) -> str | None:
    """If `body_text` is a forwarded email, return the original sender's email
    address. Returns None if the email is a reply (quoted history) or a direct
    message — in those cases the `From:` line is not the true sender.

    Used so the LLM/extractor sees the recruiter's address rather than the
    user's own address on self-forwards.
    """
    if not body_text:
        return None

    normalized = _normalize_text(body_text)
    if not normalized:
        return None

    # Apply the same preprocessing as sanitize_email_body_for_llm so we agree
    # on what counts as a "forward" vs a "reply".
    lines = _strip_noise_lines(normalized.splitlines())

    has_explicit_marker = any(
        any(p.match(line) for p in _FORWARDED_MARKERS) for line in lines
    )
    implicit_end = _find_implicit_forward_end(lines)
    if not has_explicit_marker and implicit_end is None:
        return None

    # For nested forwards (A forwards to B forwards to C), the innermost
    # From: is typically the real recruiter and the outer ones are the user
    # forwarding to themselves. Prefer the last match.
    matches = _FROM_ADDRESS_RE.findall("\n".join(lines))
    if matches:
        return matches[-1].strip().lower()
    return None


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