from __future__ import annotations

from datetime import date
import json
import logging
import re

from app.services.llm import llm_completion
from app.services.privacy_guardrails import (
    extract_forwarded_sender,
    sanitize_email_body_for_llm,
    sanitize_email_subject,
)
from app.services.schemas import ExtractedJobApplication, JobApplicationExtractionResponse

logger = logging.getLogger(__name__)

JOB_EXTRACTION_SYSTEM_PROMPT = """\
You are CommitGraph's job application extraction engine.

Given an email, detect whether it is about a specific job application and
extract a normalized job application record or status update.

Only extract emails that are clearly about a real application lifecycle:
- application confirmations
- recruiter follow-ups
- online assessments
- interview scheduling
- rejection emails
- offer emails
- withdrawal confirmations

Do NOT extract:
- generic job marketing/newsletters
- cold outreach unrelated to an active application
- networking emails with no concrete application
- campus announcements or career fair blasts

Return a list of job application updates. Most emails should return an empty list.

Statuses:
- applied
- assessment
- interview
- rejected
- offer
- withdrawn
- closed

Interpret recruiter screens / intro calls / scheduling calls after an application
as "interview" stage updates, even if the word "interview" is not explicitly used.

Rules:
- company_name should be the employer or hiring organization
- role_title should be the specific role if clear, else null
- date_applied should only be set when the email clearly indicates the application date
- event_date should be the date of the status/update email if relevant
- summary should be short and human-readable
- raw_text should be the most relevant supporting sentence(s)
- confidence_score below 0.60 should not be returned

Return ONLY valid JSON in this shape:
{
  "job_applications": [
    {
      "company_name": "Acme",
      "role_title": "Software Engineer Intern" or null,
      "status": "applied|assessment|interview|rejected|offer|withdrawn|closed",
      "summary": "Application moved to interview stage at Acme",
      "raw_text": "We would like to invite you to interview...",
      "date_applied": "YYYY-MM-DD" or null,
      "event_date": "YYYY-MM-DD" or null,
      "confidence_score": 0.0-1.0
    }
  ]
}

If there is nothing relevant, return {"job_applications": []}.

The email body you receive may already be privacy-filtered:
- only the newest relevant message may be included
- quoted history and signatures may be removed
- sensitive numbers, addresses, URLs, and tokens may be redacted
- forwarded emails have been unwrapped; treat the visible body as the real message\
"""

JOB_FEW_SHOT_EXAMPLES: list[dict[str, str]] = [
    {
        "role": "user",
        "content": json.dumps(
            {
                "account_owner_email": "me@gmail.com",
                "sender_email": "jobs@stripe.com",
                "sender_name": "Stripe Careers",
                "subject": "Thanks for applying to Stripe",
                "body_text": (
                    "Hi Jayanth,\n\n"
                    "Thanks for applying to the Software Engineer Intern role at Stripe. "
                    "We received your application on March 18, 2026.\n\n"
                    "Stripe Recruiting"
                ),
                "sent_date": "2026-03-18",
            }
        ),
    },
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "job_applications": [
                    {
                        "company_name": "Stripe",
                        "role_title": "Software Engineer Intern",
                        "status": "applied",
                        "summary": "Applied to Software Engineer Intern at Stripe",
                        "raw_text": "Thanks for applying to the Software Engineer Intern role at Stripe. We received your application on March 18, 2026.",
                        "date_applied": "2026-03-18",
                        "event_date": "2026-03-18",
                        "confidence_score": 0.97,
                    }
                ]
            }
        ),
    },
    {
        "role": "user",
        "content": json.dumps(
            {
                "account_owner_email": "me@gmail.com",
                "sender_email": "acalcagno@technisys.com",
                "sender_name": "Agustina Calcagno",
                "subject": "Jayanth, an update on your Galileo Software Engineer application",
                "body_text": (
                    "Hi Jayanth,\n\n"
                    "Thank you for applying for the Software Engineer position at Galileo!\n\n"
                    "At this time, the Software Engineer position has been filled.\n\n"
                    "We wish you the best of luck in your job search!"
                ),
                "sent_date": "2026-04-14",
            }
        ),
    },
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "job_applications": [
                    {
                        "company_name": "Galileo",
                        "role_title": "Software Engineer",
                        "status": "rejected",
                        "summary": "Software Engineer application was closed at Galileo",
                        "raw_text": "Thank you for applying for the Software Engineer position at Galileo! At this time, the Software Engineer position has been filled.",
                        "date_applied": None,
                        "event_date": "2026-04-14",
                        "confidence_score": 0.95,
                    }
                ]
            }
        ),
    },
    {
        "role": "user",
        "content": json.dumps(
            {
                "account_owner_email": "me@gmail.com",
                "sender_email": "noreply@tesla.com",
                "sender_name": "Tesla",
                "subject": "Jayanth Thank you for your interest in Tesla",
                "body_text": (
                    "Hello Jayanth,\n\n"
                    "Thank you for your interest in the Fullstack Software Engineer position at Tesla. "
                    "After carefully reviewing your application, we have decided not to move forward "
                    "with your application at this time.\n\n"
                    "We wish you all the best in your job search."
                ),
                "sent_date": "2026-04-12",
            }
        ),
    },
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "job_applications": [
                    {
                        "company_name": "Tesla",
                        "role_title": "Fullstack Software Engineer",
                        "status": "rejected",
                        "summary": "Fullstack Software Engineer application was closed at Tesla",
                        "raw_text": "Thank you for your interest in the Fullstack Software Engineer position at Tesla. We have decided not to move forward with your application at this time.",
                        "date_applied": None,
                        "event_date": "2026-04-12",
                        "confidence_score": 0.95,
                    }
                ]
            }
        ),
    },
    {
        "role": "user",
        "content": json.dumps(
            {
                "account_owner_email": "me@gmail.com",
                "sender_email": "recruiting@deltavcapital.com",
                "sender_name": "Kirk",
                "subject": "AI Engineer role at Delta-v",
                "body_text": (
                    "Hi Jayanth,\n\n"
                    "Thanks for applying to the AI Engineer role at Delta-v. "
                    "We'd love to set up a 45-minute call to learn more about you.\n\n"
                    "Please send over your availability for the next three business days.\n"
                ),
                "sent_date": "2026-04-17",
            }
        ),
    },
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "job_applications": [
                    {
                        "company_name": "Delta-v",
                        "role_title": "AI Engineer",
                        "status": "interview",
                        "summary": "Recruiter screen requested for AI Engineer at Delta-v",
                        "raw_text": "Thanks for applying to the AI Engineer role at Delta-v. We'd love to set up a 45-minute call to learn more about you. Please send over your availability for the next three business days.",
                        "date_applied": None,
                        "event_date": "2026-04-17",
                        "confidence_score": 0.95,
                    }
                ]
            }
        ),
    },
    {
        "role": "user",
        "content": json.dumps(
            {
                "account_owner_email": "me@gmail.com",
                "sender_email": "recruiting@databricks.com",
                "sender_name": "Databricks Recruiting",
                "subject": "Interview Invitation",
                "body_text": (
                    "We were impressed by your background and would like to invite you "
                    "to a first-round interview for the Backend Engineer Intern position."
                ),
                "sent_date": "2026-03-22",
            }
        ),
    },
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "job_applications": [
                    {
                        "company_name": "Databricks",
                        "role_title": "Backend Engineer Intern",
                        "status": "interview",
                        "summary": "Interview requested for Backend Engineer Intern at Databricks",
                        "raw_text": "We were impressed by your background and would like to invite you to a first-round interview for the Backend Engineer Intern position.",
                        "date_applied": None,
                        "event_date": "2026-03-22",
                        "confidence_score": 0.96,
                    }
                ]
            }
        ),
    },
    {
        "role": "user",
        "content": json.dumps(
            {
                "account_owner_email": "me@gmail.com",
                "sender_email": "newsletter@levels.fyi",
                "sender_name": "Levels",
                "subject": "Top internships this week",
                "body_text": "Here are trending internship postings and salary insights.",
                "sent_date": "2026-03-22",
            }
        ),
    },
    {"role": "assistant", "content": json.dumps({"job_applications": []})},
]

# Broadened to match "thanks for applying", "thank you for applying",
# "applied for/to", and "application for" — all followed by role/position at company.
_ROLE_AT_COMPANY_RE = re.compile(
    r"(?:thanks?(?:\s+you)?\s+for\s+applying\s+(?:for|to)|applied\s+(?:for|to)|application\s+for)"
    r"\s+the\s+(?P<role>.+?)\s+role\s+at\s+(?P<company>.+?)(?:[.!?\n]|$)",
    re.IGNORECASE,
)
_POSITION_AT_COMPANY_RE = re.compile(
    r"(?:thanks?(?:\s+you)?\s+for\s+applying\s+(?:for|to)|applied\s+(?:for|to)|application\s+for)"
    r"\s+the\s+(?P<role>.+?)\s+(?:role|position)\s+at\s+(?P<company>.+?)(?:[.!?\n]|$)",
    re.IGNORECASE,
)
_INTEREST_IN_POSITION_AT_COMPANY_RE = re.compile(
    r"(?:thank you for your interest in|thanks for your interest in)\s+the\s+(?P<role>.+?)\s+(?:role|position)\s+at\s+(?P<company>.+?)(?:[.!?\n]|$)",
    re.IGNORECASE,
)
_SUBJECT_COMPANY_ROLE_APPLICATION_RE = re.compile(
    r"(?:update on your|regarding your|your)\s+(?P<company>[A-Za-z0-9&.'\- ]+?)\s+(?P<role>[A-Za-z0-9&.'\- ]+?)\s+application(?:[.!?\n]|$)",
    re.IGNORECASE,
)
# Last-resort: "<Role Title> at <Company>" or "<Role> role at <Company>" in the
# subject. Requires a recognizable job-title keyword to avoid matching arbitrary
# "X at Y" phrases that aren't job roles.
_SUBJECT_ROLE_AT_COMPANY_RE = re.compile(
    r"(?P<role>[A-Za-z][A-Za-z0-9&+.'\- ]*?"
    r"(?:Engineer|Developer|Designer|Manager|Analyst|Scientist|Intern|Internship"
    r"|Lead|Architect|Consultant|Associate|Specialist|Director|Researcher"
    r"|Coordinator|Administrator|Strategist|Recruiter|PM|SWE|MLE))"
    r"\s+(?:role\s+)?at\s+"
    r"(?P<company>[A-Za-z0-9&.'\-][A-Za-z0-9&.'\- ]*?)"
    r"(?:\s*[-–—|:]|$|[.!?\n])",
    re.IGNORECASE,
)
_CALL_SIGNAL_RE = re.compile(
    r"(set up a .*?call|schedule (?:a|an) .*?call|share (?:your )?availability|send (?:over )?your availability|45-minute call|30-minute call|screen(?:ing)? call|first-round interview|interview)",
    re.IGNORECASE,
)
# Broadened to match the many flavors of rejection phrasing, including
# "wish you all the best" (Tesla) and "wish you the best of luck in your
# job search" (Galileo), plus common "we have decided not to move forward" forms.
_REJECTION_SIGNAL_RE = re.compile(
    r"(position has been filled|role has been filled"
    r"|we (?:have )?decided not to move forward|will not be moving forward|not moving forward"
    r"|wish you (?:the best of luck|all the best)(?: in your (?:job )?search)?"
    r"|unfortunately,?\s+we"
    r"|thank you for applying.*position has been filled)",
    re.IGNORECASE,
)


def _extract_role_company(combined: str) -> tuple[str, str] | None:
    for pattern in (
        _ROLE_AT_COMPANY_RE,
        _POSITION_AT_COMPANY_RE,
        _INTEREST_IN_POSITION_AT_COMPANY_RE,
        _SUBJECT_COMPANY_ROLE_APPLICATION_RE,
        _SUBJECT_ROLE_AT_COMPANY_RE,
    ):
        match = pattern.search(combined)
        if not match:
            continue
        role_title = match.group("role").strip(" .,:;")
        company_name = match.group("company").strip(" .,:;")
        if role_title and company_name:
            return role_title, company_name
    return None


def _heuristic_recruiter_screen_fallback(
    *,
    subject: str | None,
    body_text: str | None,
    sent_date: str | None,
) -> JobApplicationExtractionResponse | None:
    sanitized_subject = sanitize_email_subject(subject)
    sanitized_body = sanitize_email_body_for_llm(body_text)
    combined = f"{sanitized_subject}\n{sanitized_body}".strip()
    if not combined:
        return None

    role_company = _extract_role_company(combined)
    if not role_company or not _CALL_SIGNAL_RE.search(combined):
        return None

    role_title, company_name = role_company

    event_date = None
    if sent_date:
        try:
            event_date = date.fromisoformat(sent_date)
        except ValueError:
            event_date = None

    summary = f"Recruiter screen requested for {role_title} at {company_name}"
    raw_text = " ".join(
        part.strip()
        for part in [
            "Thanks for applying to the "
            f"{role_title} role at {company_name}.",
            "Please send over your availability for the next three business days."
            if re.search(r"availability", combined, re.IGNORECASE)
            else "A call was requested to learn more about you.",
        ]
        if part
    )

    return JobApplicationExtractionResponse(
        job_applications=[
            ExtractedJobApplication(
                company_name=company_name,
                role_title=role_title,
                status="interview",
                summary=summary,
                raw_text=raw_text,
                date_applied=None,
                event_date=event_date,
                confidence_score=0.9,
            )
        ]
    )


def _heuristic_rejection_fallback(
    *,
    subject: str | None,
    body_text: str | None,
    sent_date: str | None,
) -> JobApplicationExtractionResponse | None:
    sanitized_subject = sanitize_email_subject(subject)
    sanitized_body = sanitize_email_body_for_llm(body_text)
    combined = f"{sanitized_subject}\n{sanitized_body}".strip()
    if not combined or not _REJECTION_SIGNAL_RE.search(combined):
        return None

    role_company = _extract_role_company(combined)
    if not role_company:
        return None

    role_title, company_name = role_company

    event_date = None
    if sent_date:
        try:
            event_date = date.fromisoformat(sent_date)
        except ValueError:
            event_date = None

    raw_text_parts: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", sanitized_body):
        sentence = sentence.strip()
        if not sentence:
            continue
        if (
            re.search(rf"\b{re.escape(company_name)}\b", sentence, re.IGNORECASE)
            or re.search(rf"\b{re.escape(role_title)}\b", sentence, re.IGNORECASE)
            or _REJECTION_SIGNAL_RE.search(sentence)
        ):
            raw_text_parts.append(sentence)
        if len(raw_text_parts) >= 2:
            break

    raw_text = " ".join(raw_text_parts).strip()
    if not raw_text:
        raw_text = (
            f"Thank you for applying for the {role_title} position at {company_name}. "
            f"At this time, the {role_title} position has been filled."
        )

    return JobApplicationExtractionResponse(
        job_applications=[
            ExtractedJobApplication(
                company_name=company_name,
                role_title=role_title,
                status="rejected",
                summary=f"{role_title} application was closed at {company_name}",
                raw_text=raw_text,
                date_applied=None,
                event_date=event_date,
                confidence_score=0.92,
            )
        ]
    )


def _build_email_payload(
    *,
    account_owner_email: str,
    sender_email: str,
    sender_name: str | None,
    subject: str | None,
    body_text: str | None,
    sent_date: str | None,
) -> str:
    return json.dumps(
        {
            "account_owner_email": account_owner_email,
            "sender_email": sender_email,
            "sender_name": sender_name,
            "subject": sanitize_email_subject(subject),
            "body_text": sanitize_email_body_for_llm(body_text),
            "sent_date": sent_date,
        },
        ensure_ascii=False,
    )


def _parse_job_extraction_response(raw: str) -> JobApplicationExtractionResponse:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.index("\n")
        cleaned = cleaned[first_newline + 1:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return JobApplicationExtractionResponse.model_validate_json(cleaned.strip())


async def extract_job_applications(
    *,
    account_owner_email: str,
    sender_email: str,
    sender_name: str | None,
    subject: str | None,
    body_text: str | None,
    sent_date: str | None,
) -> JobApplicationExtractionResponse:
    # If this email is a forward (common when users forward recruiter emails
    # from their school/work account to their personal account), the `sender_email`
    # we receive is the forwarder, not the real recruiter. Recover the original
    # sender from the forward header so the LLM sees it correctly.
    original_sender = extract_forwarded_sender(body_text)
    effective_sender = original_sender or sender_email
    if original_sender and original_sender != sender_email.lower():
        logger.info("Detected forwarded email: using original sender from forward header")

    email_payload = _build_email_payload(
        account_owner_email=account_owner_email,
        sender_email=effective_sender,
        sender_name=sender_name,
        subject=subject,
        body_text=body_text,
        sent_date=sent_date,
    )

    # Useful debug breadcrumb — if extraction ever misses wholesale again,
    # this log tells you immediately whether the sanitizer left anything to work with.
    sanitized_body_preview = sanitize_email_body_for_llm(body_text)
    logger.debug(
        "Job extraction invoked: sanitized_body_len=%d",
        len(sanitized_body_preview),
    )

    messages = [
        {"role": "system", "content": JOB_EXTRACTION_SYSTEM_PROMPT},
        *JOB_FEW_SHOT_EXAMPLES,
        {"role": "user", "content": email_payload},
    ]

    result = await llm_completion(
        task="job_application_extraction",
        messages=messages,
        response_format={"type": "json_object"},
    )

    try:
        parsed = _parse_job_extraction_response(result.content)
        logger.info(
            "Extracted %d job application updates model=%s cost=$%.6f",
            len(parsed.job_applications),
            result.model,
            result.cost_usd,
        )
        if not parsed.job_applications:
            rejection_heuristic = _heuristic_rejection_fallback(
                subject=subject,
                body_text=body_text,
                sent_date=sent_date,
            )
            if rejection_heuristic:
                logger.info(
                    "Heuristic rejection fallback produced %d job application update(s)",
                    len(rejection_heuristic.job_applications),
                )
                return rejection_heuristic
            heuristic = _heuristic_recruiter_screen_fallback(
                subject=subject,
                body_text=body_text,
                sent_date=sent_date,
            )
            if heuristic:
                logger.info(
                    "Heuristic recruiter-screen fallback produced %d job application update(s)",
                    len(heuristic.job_applications),
                )
                return heuristic
        return parsed
    except (json.JSONDecodeError, ValueError) as first_error:
        logger.warning(
            "Job extraction invalid JSON on first attempt (model=%s): %s. Retrying...",
            result.model,
            first_error,
        )

    messages.append({"role": "assistant", "content": result.content})
    messages.append(
        {
            "role": "user",
            "content": (
                "Your response was not valid JSON. "
                "Return ONLY a raw JSON object with a 'job_applications' key."
            ),
        }
    )

    retry_result = await llm_completion(
        task="job_application_extraction",
        messages=messages,
        response_format={"type": "json_object"},
    )

    try:
        parsed = _parse_job_extraction_response(retry_result.content)
        if not parsed.job_applications:
            rejection_heuristic = _heuristic_rejection_fallback(
                subject=subject,
                body_text=body_text,
                sent_date=sent_date,
            )
            if rejection_heuristic:
                logger.info(
                    "Heuristic rejection fallback produced %d job application update(s) after retry",
                    len(rejection_heuristic.job_applications),
                )
                return rejection_heuristic
            heuristic = _heuristic_recruiter_screen_fallback(
                subject=subject,
                body_text=body_text,
                sent_date=sent_date,
            )
            if heuristic:
                logger.info(
                    "Heuristic recruiter-screen fallback produced %d job application update(s) after retry",
                    len(heuristic.job_applications),
                )
                return heuristic
        return parsed
    except (json.JSONDecodeError, ValueError) as retry_error:
        logger.error(
            "Job extraction invalid JSON on retry too (model=%s): %s. Returning empty extraction.",
            retry_result.model,
            retry_error,
        )
        rejection_heuristic = _heuristic_rejection_fallback(
            subject=subject,
            body_text=body_text,
            sent_date=sent_date,
        )
        if rejection_heuristic:
            return rejection_heuristic
        heuristic = _heuristic_recruiter_screen_fallback(
            subject=subject,
            body_text=body_text,
            sent_date=sent_date,
        )
        return heuristic or JobApplicationExtractionResponse(job_applications=[])