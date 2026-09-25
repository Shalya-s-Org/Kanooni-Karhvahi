from typing import AsyncGenerator, Dict, Any
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text
from app.core.config import settings
from app.core.logging import logger

# Async engine for FastAPI application lifecycle
try:
    engine_kwargs = {"echo": settings.DEBUG}
    if not settings.DATABASE_URL.startswith("sqlite"):
        engine_kwargs["pool_size"] = settings.DB_POOL_SIZE
        engine_kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW

    engine = create_async_engine(
        settings.DATABASE_URL,
        **engine_kwargs
    )
    AsyncSessionLocal = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
except Exception as e:
    logger.warning("Could not initialize database engine: %s", e)
    engine = None
    AsyncSessionLocal = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency yielding an async database session.
    """
    if AsyncSessionLocal is None:
        raise RuntimeError("Database engine is not configured or driver is missing.")

    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def check_database_connection() -> Dict[str, Any]:
    """
    Verifies live connectivity to the PostgreSQL database.
    """
    if engine is None:
        return {
            "connected": False,
            "message": "Database engine not initialized (driver or configuration missing)."
        }

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {
            "connected": True,
            "message": "Database ping succeeded."
        }
    except Exception as e:
        return {
            "connected": False,
            "message": f"Database connection failed: {str(e)}"
        }
