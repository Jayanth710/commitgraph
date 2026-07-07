"""Optional observability: Sentry (errors) + Langfuse (LLM traces).

Everything is gated on env config and is a no-op when keys are unset, so dev and
CI run unaffected. ``init_observability()`` is called once at the start of each
process (API, worker, scheduler).
"""

from __future__ import annotations

import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_initialized = False


def init_observability() -> None:
    global _initialized
    if _initialized:
        return
    _initialized = True

    settings = get_settings()

    if settings.sentry_dsn:
        try:
            import sentry_sdk

            sentry_sdk.init(
                dsn=settings.sentry_dsn,
                traces_sample_rate=settings.sentry_traces_sample_rate,
                environment=settings.app_env,
                # We handle inbox content — never let Sentry attach request bodies/PII.
                send_default_pii=False,
            )
            logger.info("Sentry initialized")
        except Exception:
            logger.exception("Failed to initialize Sentry")

    if settings.langfuse_public_key and settings.langfuse_secret_key:
        try:
            import os

            import litellm

            os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key)
            os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key)
            os.environ.setdefault("LANGFUSE_HOST", settings.langfuse_host)
            litellm.success_callback = list({*(litellm.success_callback or []), "langfuse"})
            litellm.failure_callback = list({*(litellm.failure_callback or []), "langfuse"})
            logger.info("Langfuse LLM tracing enabled")
        except Exception:
            logger.exception("Failed to enable Langfuse tracing")


def capture_message(message: str, level: str = "warning") -> None:
    """Send a message to Sentry if configured (no-op otherwise)."""
    if not get_settings().sentry_dsn:
        return
    try:
        import sentry_sdk

        sentry_sdk.capture_message(message, level=level)
    except Exception:
        pass
