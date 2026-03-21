import ssl as ssl_module
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import get_settings

settings = get_settings()

connect_args = {}
if settings.app_env == "production":
    ssl_ctx = ssl_module.create_default_context()
    connect_args["ssl"] = ssl_ctx

engine = create_async_engine(
    settings.async_database_url,
    pool_pre_ping=True,
    connect_args=connect_args,
)

AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session