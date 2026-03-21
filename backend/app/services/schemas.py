"""
Pydantic schemas for commitment extraction.

These models define the EXACT shape of data that flows through the pipeline:

    LLM response (JSON string)
        → ExtractionResponse (Pydantic validates it)
            → ExtractedCommitment (one per detected commitment)

Why Pydantic and not plain dicts?
    - The LLM can return malformed JSON, wrong types, missing fields.
    - Pydantic catches ALL of these at parse time with clear error messages.
    - Type hints give you IDE autocompletion everywhere downstream.
    - Field constraints (ge=0.0, le=1.0) catch nonsense values automatically.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class ExtractedCommitment(BaseModel):
    """A single commitment extracted from an email by the LLM.

    Every field here maps to a column in the commitments table
    or is used by the entity resolution / routing logic.
    """

    summary: str = Field(
        description=(
            "One-line human-readable summary of the commitment. "
            "Example: 'Send Q3 proposal draft to Sarah by Friday'"
        ),
    )

    raw_text: str = Field(
        description=(
            "The exact sentence(s) from the email that express this commitment. "
            "Copied verbatim — not paraphrased."
        ),
    )

    commitment_type: str = Field(
        description=(
            "Category of commitment. Must be one of: "
            "deliverable, follow_up, response_needed, "
            "meeting_prep, review, decision, other"
        ),
    )

    owner_email: str = Field(
        description=(
            "Email address of the person who made the commitment. "
            "Use the sender's email if they are committing to do something. "
            "Use a recipient's email if THEY committed in the email body."
        ),
    )

    target_email: str | None = Field(
        default=None,
        description=(
            "Email address of the person the commitment is directed toward. "
            "None if the commitment is general (not to a specific person)."
        ),
    )

    direction: str = Field(
        description=(
            "From the perspective of the email account owner: "
            "'outbound' = I promised someone else. "
            "'inbound' = someone else promised me."
        ),
    )

    due_date: date | None = Field(
        default=None,
        description=(
            "Inferred deadline as YYYY-MM-DD. "
            "None if no deadline is stated or implied."
        ),
    )

    due_date_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description=(
            "Confidence in the due_date inference. "
            "1.0 = explicit date stated ('by March 20'). "
            "0.5 = relative date ('by end of week'). "
            "0.0 = no date found."
        ),
    )

    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "Overall confidence that this IS a real commitment. "
            "0.9+ = clear, explicit promise ('I will send it by Friday'). "
            "0.7-0.9 = probable commitment ('I should be able to get that done'). "
            "0.5-0.7 = vague, might just be polite ('Let me look into that'). "
            "Below 0.5 = probably not a commitment."
        ),
    )


class ExtractionResponse(BaseModel):
    """Top-level response from the extraction LLM call.

    The LLM returns a JSON object with a single key 'commitments'
    containing a list of ExtractedCommitment objects.
    An empty list means no commitments were found in the email.
    """

    commitments: list[ExtractedCommitment] = Field(
        default_factory=list,
        description="List of extracted commitments. Empty list if none found.",
    )
