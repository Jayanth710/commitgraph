from __future__ import annotations

import json
import logging

from app.services.llm import llm_completion
from app.services.privacy_guardrails import (
    sanitize_email_body_for_llm,
    sanitize_email_subject,
)
from app.services.schemas import JobApplicationExtractionResponse

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
- sensitive numbers, addresses, URLs, and tokens may be redacted\
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
    email_payload = _build_email_payload(
        account_owner_email=account_owner_email,
        sender_email=sender_email,
        sender_name=sender_name,
        subject=subject,
        body_text=body_text,
        sent_date=sent_date,
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
            "Extracted %d job application updates from subject=%r model=%s cost=$%.6f",
            len(parsed.job_applications),
            subject,
            result.model,
            result.cost_usd,
        )
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
        return _parse_job_extraction_response(retry_result.content)
    except (json.JSONDecodeError, ValueError):
        logger.error(
            "Job extraction invalid JSON on retry too (model=%s). Returning empty extraction.",
            retry_result.model,
        )
        return JobApplicationExtractionResponse(job_applications=[])
