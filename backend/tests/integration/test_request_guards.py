"""Request-guard integration: rate limit + body-size cap (CLAUDE.md §2, §4).

Both guards must return the uniform §7 error envelope, and neither may throttle
the health probes (an orchestrator would read a 429 as an outage).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from app.core.config import get_settings
from app.core.dependencies import get_db
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


@pytest_asyncio.fixture
async def tight_client(
    db_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[AsyncClient]:
    """An app whose limits are small enough to trip deterministically."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "3")
    monkeypatch.setenv("REQUEST_MAX_BODY_MB", "1")
    get_settings.cache_clear()

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
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_rate_limit_returns_429_envelope(tight_client: AsyncClient) -> None:
    # Limit is 3/minute; the 4th call from the same key must be throttled.
    statuses = []
    for _ in range(5):
        resp = await tight_client.get("/api/v1/auth/me", headers={"X-Real-IP": "203.0.113.10"})
        statuses.append(resp.status_code)

    assert 429 in statuses, f"expected a throttled response, got {statuses}"
    throttled = await tight_client.get("/api/v1/auth/me", headers={"X-Real-IP": "203.0.113.10"})
    assert throttled.status_code == 429
    body = throttled.json()
    assert body["error"]["code"] == "rate_limited"
    assert "request_id" in body["error"]


@pytest.mark.asyncio
async def test_rate_limit_is_keyed_per_client(tight_client: AsyncClient) -> None:
    """One noisy client must not throttle everyone else."""
    for _ in range(5):
        await tight_client.get("/api/v1/auth/me", headers={"X-Real-IP": "198.51.100.1"})

    # A different source IP still gets served (401 for no token, not 429).
    other = await tight_client.get("/api/v1/auth/me", headers={"X-Real-IP": "198.51.100.2"})
    assert other.status_code != 429


@pytest.mark.asyncio
async def test_health_probes_are_never_throttled(tight_client: AsyncClient) -> None:
    for _ in range(10):
        resp = await tight_client.get("/api/v1/health", headers={"X-Real-IP": "203.0.113.99"})
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_oversized_body_returns_413_envelope(tight_client: AsyncClient) -> None:
    # REQUEST_MAX_BODY_MB=1 → a 2 MiB body is refused before it is buffered.
    payload = b"x" * (2 * 1024 * 1024)
    resp = await tight_client.post(
        "/api/v1/auth/login",
        content=payload,
        headers={"Content-Type": "application/json", "X-Real-IP": "203.0.113.50"},
    )
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "body_too_large"


@pytest.mark.asyncio
async def test_body_within_limit_is_not_rejected(tight_client: AsyncClient) -> None:
    resp = await tight_client.post(
        "/api/v1/auth/login",
        json={"username": "nobody", "password": "x"},
        headers={"X-Real-IP": "203.0.113.51"},
    )
    # Reaches the route and fails auth — not blocked by the size guard.
    assert resp.status_code == 401
