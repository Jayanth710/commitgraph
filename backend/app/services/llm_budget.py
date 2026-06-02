"""Per-user LLM budget.

The user whose work triggered an LLM call is carried in a contextvar (set by the
worker before extraction), so the LLM gateway can attribute and cap spend
without threading user_id through every function. Spend is tracked per user per
day in the llm_daily_spend table.
"""

from __future__ import annotations

import contextvars
import logging

from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

# Set by the worker before invoking the extraction graph; read by the LLM gateway.
current_user_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_user_id", default=None
)


class UserBudgetExceeded(RuntimeError):
    """Raised when the current user has hit their daily LLM budget."""


async def check_user_budget() -> None:
    """Raise UserBudgetExceeded if the current user is over their daily cap.

    No-op when there's no user in context or enforcement is disabled (limit<=0).
    """
    user_id = current_user_id.get()
    limit = get_settings().llm_user_daily_budget_usd
    if not user_id or limit <= 0:
        return

    async with AsyncSessionLocal() as db:
        row = (
            await db.execute(
                text(
                    "SELECT cost_usd FROM llm_daily_spend "
                    "WHERE user_id = :uid AND day = CURRENT_DATE"
                ),
                {"uid": user_id},
            )
        ).first()
    spent = float(row[0]) if row else 0.0
    if spent >= limit:
        raise UserBudgetExceeded(
            f"User {user_id} daily LLM budget exhausted: ${spent:.4f} >= ${limit:.2f}"
        )


async def record_user_spend(cost_usd: float) -> None:
    """Accumulate cost against the current user's daily total (no-op if no user)."""
    user_id = current_user_id.get()
    if not user_id or cost_usd <= 0:
        return
    try:
        async with AsyncSessionLocal() as db:
            async with db.begin():
                await db.execute(
                    text(
                        """
                        INSERT INTO llm_daily_spend (user_id, day, cost_usd)
                        VALUES (:uid, CURRENT_DATE, :cost)
                        ON CONFLICT (user_id, day) DO UPDATE
                        SET cost_usd = llm_daily_spend.cost_usd + EXCLUDED.cost_usd,
                            updated_at = now()
                        """
                    ),
                    {"uid": user_id, "cost": cost_usd},
                )
    except Exception:
        # Never let cost accounting break extraction.
        logger.exception("Failed to record LLM spend for user=%s", user_id)
