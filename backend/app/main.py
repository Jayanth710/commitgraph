from fastapi import FastAPI

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.routes.auth_user import router as user_auth_router
from app.routes.auth_google_signin import router as google_signin_router
from app.routes.auth_google import router as google_auth_router
from app.routes.auth_microsoft import router as microsoft_auth_router
from app.routes.outlook_watch import router as outlook_watch_router
from app.routes.webhooks_outlook import router as outlook_webhook_router
from app.routes.gcal_sync import router as gcal_sync_router
from app.routes.health import router as health_router
from app.routes.webhooks_gmail import router as gmail_webhook_router
from app.routes.gmail_watch import router as gmail_watch_router
from app.routes.gmail_normalize import router as gmail_normalize_router
from app.routes.api import router as api_router
from app.routes.api import router as gmail_send_router
from app.routes.api import router as admin_router
from fastapi.middleware.cors import CORSMiddleware

settings = get_settings()
setup_logging(settings.log_level)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://commitgraph-tau.vercel.app",
        "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(user_auth_router)
app.include_router(google_signin_router)
app.include_router(google_auth_router)
app.include_router(microsoft_auth_router)
app.include_router(gmail_webhook_router)
app.include_router(outlook_webhook_router)
app.include_router(gmail_watch_router)
app.include_router(outlook_watch_router)
app.include_router(gmail_normalize_router)
app.include_router(gcal_sync_router)
app.include_router(api_router)
app.include_router(gmail_send_router)
app.include_router(admin_router)