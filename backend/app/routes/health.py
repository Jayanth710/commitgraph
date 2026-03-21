from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.services.redis_streams import check_redis_health

router = APIRouter()
settings = get_settings()


@router.get("/health")
async def health() -> dict:
    db_ok = False
    redis_ok = False
    db_error = None
    redis_error = None

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT 1"))
            db_ok = result.scalar() == 1
    except Exception as e:
        db_ok = False
        db_error = str(e)

    try:
        redis_ok = await check_redis_health()
        if not redis_ok:
            redis_error = "check returned False"
    except Exception as e:
        redis_ok = False
        redis_error = str(e)

    return {
        "status": "ok" if db_ok and redis_ok else "degraded",
        "service": settings.app_name,
        "environment": settings.app_env,
        "dependencies": {
            "postgres": db_ok,
            "redis": redis_ok,
        },
        "errors": {
            "postgres": db_error,
            "redis": redis_error,
        },
    }