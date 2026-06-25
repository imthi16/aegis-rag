"""Integration-test fixtures (DB-backed + ASGI client).

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
from app.core.dependencies import get_db
from app.db.base import Base
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool


def _db_url() -> str | None:
    return os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")


@pytest_asyncio.fixture
async def db_engine() -> AsyncIterator[AsyncEngine]:
    url = _db_url()
    if not url or "asyncpg" not in url:
        pytest.skip("no asyncpg TEST_DATABASE_URL/DATABASE_URL set")

    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        await engine.dispose()
        pytest.skip("database not reachable")

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    """ASGI client whose get_db is bound to the test engine."""
    from app.main import create_app

    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
