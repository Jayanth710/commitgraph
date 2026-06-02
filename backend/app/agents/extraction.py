"""
Commitment extraction from emails.

This module contains:
    1. The extraction prompt (with few-shot examples)
    2. The function that calls the LLM and parses the response
    3. Retry logic for malformed LLM output

The prompt design follows three principles:
    - Few-shot examples teach the model what IS and ISN'T a commitment
    - Structured JSON output with a strict schema prevents free-form responses
    - The system message anchors the model's role and scoring criteria
"""

from __future__ import annotations

import json
import logging

from app.services.llm import llm_completion
from app.services.privacy_guardrails import (
    minimize_recipients_for_llm,
    sanitize_email_body_for_llm,
    sanitize_email_subject,
)
from app.services.schemas import ExtractionResponse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# System prompt — defines the LLM's role and scoring rules
# ---------------------------------------------------------------------------
EXTRACTION_SYSTEM_PROMPT = """\
You are CommitGraph's commitment extraction engine.

Your job: given an email or chat message (e.g. Slack), identify ACTIONABLE
COMMITMENTS — specific promises that someone made to do something. Return them
as structured JSON.

Chat messages have no subject and use casual phrasing; a clear action with a
deadline still counts (e.g. "I'll deploy by tomorrow", "can you review the PR by
Friday"). Senders may be identified by a username/handle rather than an email —
use whatever identifier is provided for owner_email/target_email.

## What IS a commitment:
- "I'll send the proposal by Friday" → deliverable, high confidence
- "I'll get back to you on Monday with the numbers" → follow_up, high confidence
- "Can you review this by end of week?" → review (inbound from the recipient's perspective), high confidence
- "Let me check with the team and circle back" → follow_up, medium confidence
- "Please send over your availability for the next three business days" → response_needed, high confidence

## What is NOT a commitment:
- "Thanks for the update!" → social pleasantry, NOT a commitment
- "Sounds good" → acknowledgment, NOT a commitment
- "We should grab coffee sometime" → vague social plan, NOT a commitment
- "Let me know if you have questions" → standing offer, NOT a commitment
- "Hope you're doing well" → greeting, NOT a commitment
- Newsletter content, marketing emails, automated notifications → NEVER commitments

## Scoring rules for confidence_score:
- 0.90-1.00: Explicit, unambiguous promise with a clear action ("I will send X by Y")
- 0.75-0.89: Strong implication of commitment ("I should have that ready next week")
- 0.50-0.74: Probable but vague ("Let me look into that", "I'll try to get to it").
  STILL EXTRACT these — they are routed to human review, so do not silently drop a
  plausible commitment just because it's uncertain.
- Below 0.50: Not a real commitment. Leave it out.

## Summary format:
Write 'summary' as a concise action phrase: "<verb> <object> [to <person>] [by <deadline>]".
ALWAYS include the recipient and the deadline when they are known — e.g.
"Send the Q3 report to John by Friday", NOT just "Send the report". Be specific and consistent.

## Direction rules — decide in two steps:
Step 1 — WHO must perform the action? Put that person in owner_email.
Step 2 — compare that owner to the ACCOUNT OWNER (account_owner_email):
  - owner IS the account owner  -> direction = "outbound" (the owner owes it; "I owe")
  - owner is someone else       -> direction = "inbound"  (it's owed to the account owner)

Resolve "I", "me", "you" against the account owner BEFORE deciding:
- Account owner says "I'll send X to you/them"  -> owner = account owner -> outbound.
- "Please send X to me" / "Can you do X?" addressed to the account owner
  -> the account owner must do it -> owner = account owner -> outbound.
- Someone who is NOT the account owner says "I'll send X to you" (you = account owner)
  -> owner = that sender -> inbound (it's owed TO the account owner).
- "Send the deck to me by EOD" where "me" = the account owner
  -> someone ELSE must send it -> owner = that other person -> inbound.
- Shared/mutual plans ("let's sync Friday", "we'll both review"): attribute the part the
  account owner is responsible for and pick that side; if the owner is clearly a
  participant, default to "outbound".

target_email = the person the action is owed to, if clear.

## Output format:
Return ONLY valid JSON matching this exact schema:
{
  "commitments": [
    {
      "summary": "...",
      "raw_text": "...",
      "commitment_type": "deliverable|follow_up|response_needed|meeting_prep|review|decision|other",
      "owner_email": "...",
      "target_email": "..." or null,
      "direction": "outbound|inbound",
      "due_date": "YYYY-MM-DD" or null,
      "due_date_confidence": 0.0-1.0,
      "confidence_score": 0.0-1.0
    }
  ]
}

If no commitments are found, return: {"commitments": []}

The email body you receive may already be privacy-filtered:
- only the newest relevant message may be included
- quoted history and signatures may be removed
- sensitive numbers, addresses, URLs, and tokens may be redacted

Do NOT wrap in markdown code fences. Return raw JSON only.\
"""


# ---------------------------------------------------------------------------
# Few-shot examples — the most effective prompt engineering technique
#
# These examples teach the model:
#   1. What a clear outbound commitment looks like
#   2. What an inbound commitment looks like
#   3. That newsletter/automated emails have NO commitments
#   4. That vague social plans are NOT commitments
#   5. How to handle multiple commitments in one email
# ---------------------------------------------------------------------------
FEW_SHOT_EXAMPLES: list[dict[str, str]] = [
    # Example 1: Clear outbound commitment with deadline
    {
        "role": "user",
        "content": json.dumps({
            "account_owner_email": "me@gmail.com",
            "sender_email": "me@gmail.com",
            "sender_name": "Me",
            "recipients": [{"email": "sarah@company.com", "name": "Sarah Chen", "type": "to"}],
            "subject": "Re: Q3 Proposal",
            "body_text": (
                "Hi Sarah,\n\n"
                "Thanks for the feedback. I'll have the revised proposal to you "
                "by end of day Friday. I'll also include the updated budget numbers "
                "that finance sent over.\n\n"
                "Best,\nMe"
            ),
            "sent_date": "2026-03-17",
        }),
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "commitments": [
                {
                    "summary": "Send revised Q3 proposal with updated budget numbers to Sarah",
                    "raw_text": "I'll have the revised proposal to you by end of day Friday. I'll also include the updated budget numbers that finance sent over.",
                    "commitment_type": "deliverable",
                    "owner_email": "me@gmail.com",
                    "target_email": "sarah@company.com",
                    "direction": "outbound",
                    "due_date": "2026-03-20",
                    "due_date_confidence": 0.85,
                    "confidence_score": 0.95,
                },
            ],
        }),
    },
    # Example 2: Inbound commitment — someone promises to the account owner
    {
        "role": "user",
        "content": json.dumps({
            "account_owner_email": "me@gmail.com",
            "sender_email": "david@partner.io",
            "sender_name": "David Park",
            "recipients": [{"email": "me@gmail.com", "name": "Me", "type": "to"}],
            "subject": "API Integration Timeline",
            "body_text": (
                "Hey,\n\n"
                "I spoke with our engineering lead. We'll have the sandbox API "
                "credentials ready for you by next Tuesday. I'll send them over "
                "as soon as they're provisioned.\n\n"
                "Cheers,\nDavid"
            ),
            "sent_date": "2026-03-17",
        }),
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "commitments": [
                {
                    "summary": "David will send sandbox API credentials",
                    "raw_text": "We'll have the sandbox API credentials ready for you by next Tuesday. I'll send them over as soon as they're provisioned.",
                    "commitment_type": "deliverable",
                    "owner_email": "david@partner.io",
                    "target_email": "me@gmail.com",
                    "direction": "inbound",
                    "due_date": "2026-03-24",
                    "due_date_confidence": 0.80,
                    "confidence_score": 0.92,
                },
            ],
        }),
    },
    # Example 3: Newsletter — no commitments at all
    {
        "role": "user",
        "content": json.dumps({
            "account_owner_email": "me@gmail.com",
            "sender_email": "newsletter@techdigest.com",
            "sender_name": "Tech Digest Weekly",
            "recipients": [{"email": "me@gmail.com", "name": None, "type": "to"}],
            "subject": "This Week in AI: March 17, 2026",
            "body_text": (
                "TOP STORIES THIS WEEK\n\n"
                "1. OpenAI announces GPT-5 preview\n"
                "2. Google DeepMind publishes new robotics paper\n"
                "3. EU AI Act enforcement begins next month\n\n"
                "Read more at techdigest.com"
            ),
            "sent_date": "2026-03-17",
        }),
    },
    {
        "role": "assistant",
        "content": json.dumps({"commitments": []}),
    },
    # Example 4: Vague social — NOT a commitment
    {
        "role": "user",
        "content": json.dumps({
            "account_owner_email": "me@gmail.com",
            "sender_email": "alex@friend.com",
            "sender_name": "Alex",
            "recipients": [{"email": "me@gmail.com", "name": "Me", "type": "to"}],
            "subject": "Re: Catching up",
            "body_text": (
                "Hey! Great to hear from you.\n\n"
                "We should definitely grab lunch sometime soon. "
                "It's been way too long! Let me know when you're free.\n\n"
                "Alex"
            ),
            "sent_date": "2026-03-17",
        }),
    },
    {
        "role": "assistant",
        "content": json.dumps({"commitments": []}),
    },
     # Example: Sender assigns work to the account owner
    {
            "role": "user",
            "content": json.dumps({
                "account_owner_email": "me@gmail.com",
                "sender_email": "david@partner.io",
                "sender_name": "David",
                "recipients": [{"email": "me@gmail.com", "name": "Me", "type": "to"}],
                "subject": "Action items",
                "body_text": (
                    "Hi,\n\n"
                    "You need to write the API tests by March 30th.\n\n"
                    "Thanks,\nDavid"
                ),
                "sent_date": "2026-03-20",
            }),
        },
        {
            "role": "assistant",
            "content": json.dumps({
                "commitments": [
                    {
                        "summary": "Write the API tests",
                        "raw_text": "You need to write the API tests by March 30th.",
                        "commitment_type": "deliverable",
                        "owner_email": "me@gmail.com",
                        "target_email": "david@partner.io",
                        "direction": "outbound",
                        "due_date": "2026-03-30",
                        "due_date_confidence": 0.95,
                        "confidence_score": 0.95,
                    }
                ]
            }),
        },
    # Example: recruiter asks the account owner to send availability
    {
        "role": "user",
        "content": json.dumps({
            "account_owner_email": "me@gmail.com",
            "sender_email": "recruiting@deltavcapital.com",
            "sender_name": "Kirk",
            "recipients": [{"email": "me@gmail.com", "name": "Me", "type": "to"}],
            "subject": "AI Engineer role at Delta-v",
            "body_text": (
                "Hi,\n\n"
                "Thanks for applying to the AI Engineer role at Delta-v. "
                "We'd love to set up a 45-minute call to learn more about you.\n\n"
                "Please send over your availability for the next three business days. "
                "I look forward to chatting live.\n"
            ),
            "sent_date": "2026-04-17",
        }),
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "commitments": [
                {
                    "summary": "Send availability for a 45-minute call with Delta-v",
                    "raw_text": "Please send over your availability for the next three business days.",
                    "commitment_type": "response_needed",
                    "owner_email": "me@gmail.com",
                    "target_email": "recruiting@deltavcapital.com",
                    "direction": "outbound",
                    "due_date": None,
                    "due_date_confidence": 0.0,
                    "confidence_score": 0.91,
                }
            ]
        }),
    },
    # Example: chat/Slack message the ACCOUNT OWNER sent — their own promise is
    # outbound ("I owe"). Sender matches account_owner_email, so direction=outbound.
    {
        "role": "user",
        "content": json.dumps({
            "account_owner_email": "slack:U07ABC",
            "sender_email": "slack:U07ABC",
            "sender_name": "U07ABC",
            "recipients": [],
            "subject": "(no subject)",
            "body_text": (
                "Hey team, I'll get the deployment done by tomorrow and "
                "send the review notes by Friday."
            ),
            "sent_date": "2026-06-01",
        }),
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "commitments": [
                {
                    "summary": "Complete the deployment",
                    "raw_text": "I'll get the deployment done by tomorrow",
                    "commitment_type": "deliverable",
                    "owner_email": "slack:U07ABC",
                    "target_email": None,
                    "direction": "outbound",
                    "due_date": "2026-06-02",
                    "due_date_confidence": 0.8,
                    "confidence_score": 0.85,
                },
                {
                    "summary": "Send the review notes",
                    "raw_text": "send the review notes by Friday",
                    "commitment_type": "deliverable",
                    "owner_email": "slack:U07ABC",
                    "target_email": None,
                    "direction": "outbound",
                    "due_date": None,
                    "due_date_confidence": 0.0,
                    "confidence_score": 0.8,
                },
            ]
        }),
    },
    # Example: someone else promises a deliverable TO the account owner -> inbound
    {
        "role": "user",
        "content": json.dumps({
            "account_owner_email": "me@gmail.com",
            "sender_email": "dana@partner.io",
            "sender_name": "Dana",
            "recipients": [{"email": "me@gmail.com", "name": "Me", "type": "to"}],
            "subject": "Onboarding deck",
            "body_text": "Hi — I'll get the onboarding deck over to you by end of day tomorrow.",
            "sent_date": "2026-04-20",
        }),
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "commitments": [
                {
                    "summary": "Send the onboarding deck to me by end of day tomorrow",
                    "raw_text": "I'll get the onboarding deck over to you by end of day tomorrow.",
                    "commitment_type": "deliverable",
                    "owner_email": "dana@partner.io",
                    "target_email": "me@gmail.com",
                    "direction": "inbound",
                    "due_date": "2026-04-21",
                    "due_date_confidence": 0.85,
                    "confidence_score": 0.9,
                }
            ]
        }),
    },
    # Example: informational FYI / announcement -> NOT a commitment
    {
        "role": "user",
        "content": json.dumps({
            "account_owner_email": "me@gmail.com",
            "sender_email": "ops@company.com",
            "sender_name": "Ops",
            "recipients": [{"email": "me@gmail.com", "name": None, "type": "to"}],
            "subject": "Maintenance window",
            "body_text": (
                "Heads up: the staging environment will be down for maintenance "
                "this weekend. No action needed on your end."
            ),
            "sent_date": "2026-04-20",
        }),
    },
    {
        "role": "assistant",
        "content": json.dumps({"commitments": []}),
    },
]


# ---------------------------------------------------------------------------
# Extraction function
# ---------------------------------------------------------------------------
def _build_email_payload(
    *,
    account_owner_email: str,
    sender_email: str,
    sender_name: str | None,
    recipients: list[dict],
    subject: str | None,
    body_text: str | None,
    sent_date: str | None,
) -> str:
    """Build the JSON payload that gets sent to the LLM as the user message."""
    return json.dumps(
        {
            "account_owner_email": account_owner_email,
            "sender_email": sender_email,
            "sender_name": sender_name,
            "recipients": minimize_recipients_for_llm(recipients),
            "subject": sanitize_email_subject(subject),
            "body_text": sanitize_email_body_for_llm(body_text),
            "sent_date": sent_date,
        },
        ensure_ascii=False,
    )


async def extract_commitments(
    *,
    account_owner_email: str,
    sender_email: str,
    sender_name: str | None,
    recipients: list[dict],
    subject: str | None,
    body_text: str | None,
    sent_date: str | None,
) -> ExtractionResponse:
    """
    Extract commitments from a single email.

    This is the core AI function of CommitGraph. It:
    1. Builds a message list: system prompt + few-shot examples + this email
    2. Calls the LLM via llm_completion (which handles model routing/fallbacks)
    3. Parses the JSON response into Pydantic models
    4. Retries once if the LLM returns invalid JSON

    Returns:
        ExtractionResponse with a list of ExtractedCommitment objects.
        May be empty if no commitments were found.
    """
    email_payload = _build_email_payload(
        account_owner_email=account_owner_email,
        sender_email=sender_email,
        sender_name=sender_name,
        recipients=recipients,
        subject=subject,
        body_text=body_text,
        sent_date=sent_date,
    )

    messages = [
        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
        *FEW_SHOT_EXAMPLES,
        {"role": "user", "content": email_payload},
    ]

    # First attempt.
    result = await llm_completion(
        task="commitment_extraction",
        messages=messages,
        response_format={"type": "json_object"},
    )

    try:
        parsed = _parse_extraction_response(result.content)
        logger.info(
            "Extracted %d commitments model=%s cost=$%.6f",
            len(parsed.commitments),
            result.model,
            result.cost_usd,
        )
        return parsed

    except (json.JSONDecodeError, ValueError) as first_error:
        logger.warning(
            "LLM returned invalid JSON on first attempt (model=%s): %s. Retrying...",
            result.model,
            first_error,
        )

    # Retry with an explicit correction message.
    messages.append({"role": "assistant", "content": result.content})
    messages.append({
        "role": "user",
        "content": (
            "Your response was not valid JSON. "
            "Return ONLY a raw JSON object with a 'commitments' key. "
            "No markdown, no explanation, no code fences."
        ),
    })

    retry_result = await llm_completion(
        task="commitment_extraction",
        messages=messages,
        response_format={"type": "json_object"},
    )

    try:
        parsed = _parse_extraction_response(retry_result.content)
        logger.info(
            "Retry succeeded: %d commitments",
            len(parsed.commitments),
        )
        return parsed

    except (json.JSONDecodeError, ValueError) as retry_error:
        logger.error(
            "LLM returned invalid JSON on retry too (model=%s): %s. "
            "Returning empty extraction.",
            retry_result.model,
            retry_error,
        )
        return ExtractionResponse(commitments=[])


def _parse_extraction_response(raw: str) -> ExtractionResponse:
    """Parse the LLM's raw string into a validated ExtractionResponse.

    Handles common LLM quirks:
    - Markdown code fences around JSON
    - Extra whitespace
    - Minor schema deviations that Pydantic can coerce
    """
    cleaned = raw.strip()

    # Strip markdown code fences if the LLM wrapped its response.
    if cleaned.startswith("```"):
        # Remove opening fence (```json or ```)
        first_newline = cleaned.index("\n")
        cleaned = cleaned[first_newline + 1:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]

    cleaned = cleaned.strip()

    # Parse and validate via Pydantic.
    return ExtractionResponse.model_validate_json(cleaned)
