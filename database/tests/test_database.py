"""Tests for database connectivity, health checks, and engine configuration."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import check_database_health


@pytest.mark.asyncio
async def test_database_health_check_healthy():
    """Verify that check_database_health returns healthy status and postgres version."""
    health = await check_database_health()
    assert health["status"] == "healthy"
    assert health["connected"] is True
    assert "latency_ms" in health
    assert "PostgreSQL" in health["postgres_version"]


@pytest.mark.asyncio
async def test_raw_query_execution(db_session: AsyncSession):
    """Verify that queries execute cleanly on the session."""
    result = await db_session.execute(text("SELECT 42 AS answer;"))
    val = result.scalar_one()
    assert val == 42


@pytest.mark.asyncio
async def test_utc_timezone_awareness(db_session: AsyncSession):
    """Verify PostgreSQL server timezone and current timestamp."""
    result = await db_session.execute(text("SELECT NOW();"))
    now = result.scalar_one()
    assert now is not None
    assert now.tzinfo is not None
