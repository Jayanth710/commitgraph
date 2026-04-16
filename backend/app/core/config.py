from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_GOOGLE_OAUTH_SCOPE = (
    "https://www.googleapis.com/auth/gmail.readonly "
    "https://www.googleapis.com/auth/calendar.readonly "
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

    gcp_project_id: str = ""
    gcp_pubsub_topic: str = "commitgraph-gmail"
    public_webhook_base_url: str = ""

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

    # --- Confidence threshold ---
    commitment_confidence_threshold: float = 0.8

    # --- JWT Auth ---
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24 hours

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
    )

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
