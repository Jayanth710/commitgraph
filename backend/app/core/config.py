from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CommitGraph API"
    app_env: str = "local"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    database_url: str
    redis_url: str

    secret_key: str
    encryption_key: str

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"
    google_oauth_scope: str = "https://www.googleapis.com/auth/gmail.readonly"

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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()