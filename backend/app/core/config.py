import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_GOOGLE_OAUTH_SCOPE = (
    "https://www.googleapis.com/auth/gmail.readonly "
    # calendar.events grants read + write on events (needed to create/delete
    # commitment reminders); it also covers the read-only sync via events.list.
    "https://www.googleapis.com/auth/calendar.events "
    "https://www.googleapis.com/auth/gmail.send"
)


class Settings(BaseSettings):
    app_name: str = "CommitGraph API"
    app_env: str = "local"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"


    frontend_url: str

    database_url: str
    redis_url: str
    # --- Upstash REST (for production) ---
    upstash_redis_rest_url: str = ""
    upstash_redis_rest_token: str = ""

    secret_key: str
    encryption_key: str

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"
    google_oauth_scope: str = DEFAULT_GOOGLE_OAUTH_SCOPE

    # --- Microsoft OAuth ---
    ms_client_id: str = ""
    ms_client_secret: str = ""
    ms_redirect_uri: str = "http://localhost:8000/auth/microsoft/callback"
    ms_tenant_id: str = "common"

    # --- Slack (a connected source, not a login) ---
    slack_client_id: str = ""
    slack_client_secret: str = ""
    slack_signing_secret: str = ""
    slack_redirect_uri: str = "http://localhost:8000/auth/slack/callback"
    slack_scopes: str = (
        "channels:history,channels:read,channels:join,groups:history,"
        "im:history,mpim:history,users:read,team:read"
    )

    gcp_project_id: str = ""
    gcp_pubsub_topic: str = "commitgraph-gmail"
    public_webhook_base_url: str = ""

    # --- Webhook authentication ---
    # Service account email that Google Pub/Sub signs push OIDC tokens with.
    # When set (or in production), the Gmail webhook rejects unsigned requests.
    pubsub_verification_email: str = ""
    # Audience configured on the Pub/Sub push subscription (usually the webhook
    # URL). When empty, audience is not checked but signature/issuer/email are.
    pubsub_audience: str = ""
    # High-entropy shared secret echoed back in Outlook Graph notifications.
    outlook_client_state: str = ""

    redis_url: str = "redis://localhost:6379/0"

    stream_ingest_raw: str = "ingest:raw"
    stream_process_normalized: str = "process:normalized"

    stream_normalizer_group: str = "normalizer"
    stream_extractor_group: str = "extractor"

    stream_normalizer_consumer: str = "normalizer-1"
    stream_extractor_consumer: str = "extractor-1"

    stream_block_ms: int = 5000
    stream_read_count: int = 10

    # For crash/redelivery testing.
    stream_debug_crash_before_ack: bool = False

    # --- LLM API keys ---
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # --- LLM budget ---
    llm_daily_budget_usd: float = 2.00
    llm_budget_alert_usd: float = 1.50
    # Per-user daily cap (USD). 0 disables per-user enforcement.
    llm_user_daily_budget_usd: float = 2.00

    # --- Confidence threshold ---
    commitment_confidence_threshold: float = 0.8

    # --- Watch subscription renewal ---
    # Renew Gmail/Outlook watches that expire within this window.
    watch_renewal_buffer_seconds: int = 86400  # 24h
    # How often the scheduler checks for watches due for renewal.
    watch_renewal_interval_seconds: int = 600  # 10m

    # --- JWT Auth ---
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24 hours
    # Name of the httpOnly cookie that carries the JWT.
    auth_cookie_name: str = "commitgraph_token"

    # --- CORS / CSRF ---
    # Comma-separated list of allowed browser origins.
    cors_allowed_origins: str = "https://commitgraph-tau.vercel.app,http://localhost:3000"

    # --- Rate limiting (per client IP, fixed window of 60s) ---
    rate_limit_default_per_min: int = 240
    rate_limit_auth_per_min: int = 10

    # --- Observability (all optional; disabled until keys are set) ---
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.0
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    google_signin_redirect_uri: str = "http://localhost:8000/auth/google-signin/callback"
    google_signin_scope: str = "openid email profile"

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        # When SECRETS_DIR is set (e.g. a Google Secret Manager / Docker / k8s
        # secret mounted as files), each setting can be read from a file named
        # after it — keeping secrets like SECRET_KEY out of plaintext env vars.
        # Unset locally -> no-op, env vars are used as before.
        secrets_dir=os.environ.get("SECRETS_DIR") or None,
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def effective_outlook_client_state(self) -> str:
        """Shared secret echoed in Outlook notifications; falls back to a
        legacy default so existing subscriptions keep validating in dev."""
        return self.outlook_client_state or "commitgraph-outlook-webhook"

    @property
    def async_database_url(self) -> str:
        url = self.database_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        # Remove query params that asyncpg doesn't understand
        if "?" in url:
            url = url.split("?")[0]
        return url

@lru_cache
def get_settings() -> Settings:
    return Settings()
