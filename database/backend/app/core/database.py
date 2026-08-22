"""SQLAlchemy 2.x async engine, session lifecycle, and health check utilities."""

import time
from typing import AsyncGenerator, Dict, Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# Create the async engine with pooling
engine: AsyncEngine = create_async_engine(
    settings.async_database_url,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    echo=settings.DB_ECHO,
    future=True,
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async session with automatic rollback on error and proper closing."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_database_health() -> Dict[str, Any]:
    """Verify database connectivity without exposing sensitive credentials."""
    start_time = time.perf_counter()
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1 AS is_alive, version() AS pg_version;"))
            row = result.mappings().one()
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return {
                "status": "healthy",
                "connected": True,
                "latency_ms": elapsed_ms,
                "postgres_version": row["pg_version"].split()[0] + " " + row["pg_version"].split()[1],
            }
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "status": "unhealthy",
            "connected": False,
            "latency_ms": elapsed_ms,
            "error": str(exc.__class__.__name__),
        }


async def close_database_engine() -> None:
    """Dispose of the database connection pool cleanly."""
    await engine.dispose()
