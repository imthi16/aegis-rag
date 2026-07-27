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
from app.db.audit_ddl import (
    AUDIT_MUTATION_GUARD_FN,
    AUDIT_MUTATION_GUARD_TRIGGER,
    DROP_AUDIT_MUTATION_GUARD_FN,
)
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
        # create_all builds tables from the model metadata but NOT the raw-SQL
        # objects the baseline migration adds. The append-only guard on
        # audit_log is a production security control (Golden Rule 5), so the
        # integration suite must run against it rather than an unprotected
        # table — otherwise a regression that drops the trigger still passes.
        await conn.execute(text(AUDIT_MUTATION_GUARD_FN))
        await conn.execute(text(AUDIT_MUTATION_GUARD_TRIGGER))
    try:
        yield engine
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.execute(text(DROP_AUDIT_MUTATION_GUARD_FN))
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture
def app_sessions(db_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch) -> None:
    """Bind the app's module-level session factory to the test engine.

    Work that outlives the request — eval background runs, the audit export's
    streaming generator — cannot use the request-scoped session, so it opens one
    from ``AsyncSessionLocal``. That points at the real ``DATABASE_URL``, so
    without this rebinding those writes/reads bypass the test database entirely.
    """
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    for module in ("app.api.v1.routes.eval", "app.api.v1.routes.audit"):
        monkeypatch.setattr(f"{module}.AsyncSessionLocal", factory)
    return None


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
