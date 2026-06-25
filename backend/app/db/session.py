"""Async engine + session factories (CLAUDE.md §6.2, §6.15).

Two engines:
  * the application engine (``aegis_app`` role) for all normal reads/writes;
  * a dedicated least-privilege audit engine (``aegis_audit`` role) used solely
    by the audit logger, so the append-only ``audit_log`` cannot be mutated even
    by buggy application code (defense in depth — §8 grants enforce it too).

``get_db`` is the FastAPI dependency; ``ping_db`` backs the readiness probe.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings, get_settings


def _audit_database_url(settings: Settings) -> str:
    """Build the audit-role DSN from parts (same host/db, restricted user)."""
    return (
        f"postgresql+asyncpg://{settings.audit_db_user}:{settings.audit_db_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
    )


@lru_cache
def get_engine() -> AsyncEngine:
    """Process-wide application engine (cached)."""
    settings = get_settings()
    url = settings.database_url
    if url is None:  # built by the config validator; defensive (fail closed)
        raise RuntimeError("database_url is not configured")
    return create_async_engine(
        url,
        echo=False,
        pool_pre_ping=True,
        future=True,
    )


@lru_cache
def get_audit_engine() -> AsyncEngine:
    """Process-wide audit engine using the least-privilege role (cached)."""
    settings = get_settings()
    return create_async_engine(
        _audit_database_url(settings),
        echo=False,
        pool_pre_ping=True,
        future=True,
    )


@lru_cache
def _app_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=get_engine(),
        expire_on_commit=False,
        autoflush=False,
    )


@lru_cache
def _audit_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=get_audit_engine(),
        expire_on_commit=False,
        autoflush=False,
    )


def AsyncSessionLocal() -> AsyncSession:  # noqa: N802 (factory, named like a class)
    """Open a new application session (caller manages the lifecycle)."""
    return _app_sessionmaker()()


def AuditSessionLocal() -> AsyncSession:  # noqa: N802
    """Open a new audit session bound to the least-privilege engine."""
    return _audit_sessionmaker()()


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yield a session, always close it."""
    session = AsyncSessionLocal()
    try:
        yield session
    finally:
        await session.close()


async def ping_db() -> bool:
    """Readiness check: can we round-trip a trivial query? (health.py)."""
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def dispose_engines() -> None:
    """Dispose engines on shutdown (lifespan)."""
    await get_engine().dispose()
    await get_audit_engine().dispose()
