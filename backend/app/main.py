from fastapi import FastAPI

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.routes.auth_google import router as google_auth_router
from app.routes.health import router as health_router
from app.routes.webhooks_gmail import router as gmail_webhook_router
from app.routes.gmail_watch import router as gmail_watch_router
from app.routes.gmail_normalize import router as gmail_normalize_router

settings = get_settings()
setup_logging(settings.log_level)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
)

app.include_router(health_router)
app.include_router(google_auth_router)
app.include_router(gmail_webhook_router)
app.include_router(gmail_watch_router)
app.include_router(gmail_normalize_router)