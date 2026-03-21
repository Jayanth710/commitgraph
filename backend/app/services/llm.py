"""
LLM gateway for CommitGraph.

Wraps LiteLLM to provide:
- Task-based model routing (cheap models for extraction, strong for reconciliation)
- Automatic fallback chains (if primary model fails, try the next one)
- Cost tracking per call
- A single function the rest of the codebase calls

Usage:
    from app.services.llm import llm_completion

    result = await llm_completion(
        task="commitment_extraction",
        messages=[{"role": "user", "content": "..."}],
    )
    # result.content  -> the LLM's response text
    # result.model    -> which model actually answered
    # result.usage    -> token counts
    # result.cost     -> estimated cost in USD
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import litellm

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LiteLLM configuration
# ---------------------------------------------------------------------------
# Suppress LiteLLM's noisy default logging.
litellm.suppress_debug_info = True
litellm.set_verbose = False


# ---------------------------------------------------------------------------
# Model routing table
#
# Each task maps to a primary model + ordered fallback list.
# The worker calls llm_completion(task="commitment_extraction", messages=[...])
# and this module picks the right model chain.
#
# Why different models per task:
#   - Extraction runs ~100x/day on every email → needs to be cheap
#   - Reconciliation runs ~10x/day on ambiguous cases → needs to be smart
#   - Answer synthesis is user-facing → quality matters most
# ---------------------------------------------------------------------------
ROUTING_TABLE: dict[str, dict[str, Any]] = {
    "commitment_extraction": {
        "model": "gpt-4o-mini",
        # Added anthropic/ prefix here
        "fallbacks": ["anthropic/claude-haiku-4-5-20241022", "gemini/gemini-2.0-flash"],
        "max_tokens": 1024,
        "temperature": 0.1,   
    },
    "commitment_reconciliation": {
        # Added anthropic/ prefix here
        "model": "anthropic/claude-sonnet-4-20250514",
        "fallbacks": ["gpt-4o"],
        "max_tokens": 2048,
        "temperature": 0.2,
    },
    "answer_synthesis": {
        # Added anthropic/ prefix here
        "model": "anthropic/claude-sonnet-4-20250514",
        "fallbacks": ["gpt-4o"],
        "max_tokens": 4096,
        "temperature": 0.3,
    },
}


# ---------------------------------------------------------------------------
# Response wrapper
# ---------------------------------------------------------------------------
@dataclass
class LLMResult:
    """Normalized result from any LLM provider."""

    content: str                         # The response text
    model: str                           # Which model actually answered
    task: str                            # Which task was requested
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    raw_response: Any = field(default=None, repr=False)


# ---------------------------------------------------------------------------
# Daily cost tracker (in-memory, resets on process restart)
#
# For a personal single-user tool this is sufficient.
# A production multi-user system would track this in the database.
# ---------------------------------------------------------------------------
_daily_cost_usd: float = 0.0


def get_daily_cost() -> float:
    return _daily_cost_usd


def reset_daily_cost() -> None:
    global _daily_cost_usd
    _daily_cost_usd = 0.0


# ---------------------------------------------------------------------------
# Core completion function
# ---------------------------------------------------------------------------
async def llm_completion(
    task: str,
    messages: list[dict[str, str]],
    *,
    response_format: dict | None = None,
    override_model: str | None = None,
) -> LLMResult:
    """
    Call an LLM using the routing table for the given task.

    Args:
        task: Key into ROUTING_TABLE (e.g. "commitment_extraction").
        messages: Standard chat messages list.
        response_format: Optional JSON mode / structured output config.
            For OpenAI: {"type": "json_object"}
            LiteLLM normalizes this across providers.
        override_model: Skip routing and use this model directly (for testing).

    Returns:
        LLMResult with content, model, token usage, and cost.

    Raises:
        ValueError: If task is not in ROUTING_TABLE.
        Exception: If all models in the fallback chain fail.
    """
    global _daily_cost_usd
    settings = get_settings()

    route = ROUTING_TABLE.get(task)
    if route is None and override_model is None:
        raise ValueError(
            f"Unknown LLM task: {task!r}. "
            f"Available tasks: {list(ROUTING_TABLE.keys())}"
        )

    # Budget guard — refuse to call if daily limit exceeded.
    if _daily_cost_usd >= settings.llm_daily_budget_usd:
        raise RuntimeError(
            f"Daily LLM budget exhausted: ${_daily_cost_usd:.4f} "
            f">= ${settings.llm_daily_budget_usd:.2f}"
        )

    # Build the model list: primary + fallbacks.
    if override_model:
        models_to_try = [override_model]
        max_tokens = 1024
        temperature = 0.2
    else:
        models_to_try = [route["model"]] + route.get("fallbacks", [])
        max_tokens = route.get("max_tokens", 1024)
        temperature = route.get("temperature", 0.2)

    # Set API keys so LiteLLM can find them.
    # LiteLLM reads these from environment or from litellm.api_key etc.
    # We set them explicitly from our settings to keep config centralized.
    if settings.openai_api_key:
        litellm.openai_key = settings.openai_api_key
    if settings.anthropic_api_key:
        litellm.anthropic_key = settings.anthropic_api_key

    # Try each model in order until one succeeds.
    last_error: Exception | None = None

    for model_name in models_to_try:
        try:
            kwargs: dict[str, Any] = {
                "model": model_name,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if response_format is not None:
                kwargs["response_format"] = response_format

            logger.info(
                "LLM call task=%s model=%s input_messages=%d",
                task,
                model_name,
                len(messages),
            )

            # litellm.acompletion is the async version of litellm.completion.
            response = await litellm.acompletion(**kwargs)

            # Extract response content.
            content = response.choices[0].message.content or ""

            # Extract token usage.
            usage = response.usage
            input_tokens = usage.prompt_tokens if usage else 0
            output_tokens = usage.completion_tokens if usage else 0
            total_tokens = usage.total_tokens if usage else 0

            # Calculate cost using LiteLLM's built-in cost calculator.
            try:
                cost = litellm.completion_cost(completion_response=response)
            except Exception:
                cost = 0.0

            _daily_cost_usd += cost

            # Warn if approaching budget limit.
            if _daily_cost_usd >= settings.llm_budget_alert_usd:
                logger.warning(
                    "LLM daily spend alert: $%.4f / $%.2f",
                    _daily_cost_usd,
                    settings.llm_daily_budget_usd,
                )

            result = LLMResult(
                content=content,
                model=model_name,
                task=task,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cost_usd=cost,
                raw_response=response,
            )

            logger.info(
                "LLM response task=%s model=%s tokens=%d/%d cost=$%.6f",
                task,
                model_name,
                input_tokens,
                output_tokens,
                cost,
            )

            return result

        except Exception as exc:
            logger.warning(
                "LLM model %s failed for task %s: %s",
                model_name,
                task,
                exc,
            )
            last_error = exc
            continue

    # All models failed.
    raise RuntimeError(
        f"All LLM models failed for task {task!r}. "
        f"Tried: {models_to_try}. Last error: {last_error}"
    )
