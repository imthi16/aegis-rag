"""Integration-test fixtures (DB-backed).

These tests need a reachable Postgres. Set ``TEST_DATABASE_URL`` (or
``DATABASE_URL``) to an asyncpg DSN; when none is reachable the fixtures skip,
so the unit suite still runs anywhere. CI provisions a postgres service.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import app.db.models  # noqa: F401  (register tables)
import pytest
import pytest_asyncio
from app.db.base import Base
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool


def _db_url() -> str | None:
    return os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    url = _db_url()
    if not url:
        pytest.skip("no TEST_DATABASE_URL/DATABASE_URL set")
    if "asyncpg" not in url:
        pytest.skip("integration tests require an asyncpg DSN")

    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        await engine.dispose()
        pytest.skip("database not reachable")

    # Fresh schema for the test (create_all mirrors the migration metadata).
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            yield session
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()
