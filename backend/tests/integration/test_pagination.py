"""Pagination bounds on every list endpoint (CLAUDE.md §7).

Unvalidated page/size reached Postgres as ``OFFSET -20`` / ``LIMIT -5``, which
raises and surfaced as a 500 with an unhandled DBAPIError instead of the uniform
§7 error envelope; an unbounded ``size`` let a single request pull a whole table.
Every list endpoint must now reject out-of-range values at the boundary.
"""

from __future__ import annotations

import pytest
from app.core.security import hash_password
from app.db.models import Role, User
from app.schemas.pagination import MAX_PAGE_SIZE
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

_PASSWORD = "pagination-pw-123"

# Every paginated endpoint in §7. audit already validated; the rest did not.
_LIST_ENDPOINTS = [
    "/api/v1/admin/users",
    "/api/v1/documents",
    "/api/v1/eval/runs",
    "/api/v1/audit",
]

_BAD_PARAMS = [
    {"page": 0},
    {"page": -1},
    {"size": 0},
    {"size": -5},
    {"size": MAX_PAGE_SIZE + 1},
    {"size": 100_000},
]


async def _admin_token(client: AsyncClient, db: AsyncSession) -> str:
    role = Role(name="admin", description="admin")
    db.add(role)
    await db.flush()
    db.add(
        User(
            username="pgadmin",
            hashed_password=hash_password(_PASSWORD),
            is_active=True,
            roles=[role],
        )
    )
    await db.commit()
    resp = await client.post(
        "/api/v1/auth/login", json={"username": "pgadmin", "password": _PASSWORD}
    )
    assert resp.status_code == 200, resp.text
    return str(resp.json()["access_token"])


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", _LIST_ENDPOINTS)
@pytest.mark.parametrize("params", _BAD_PARAMS)
async def test_out_of_range_pagination_is_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
    endpoint: str,
    params: dict[str, int],
) -> None:
    token = await _admin_token(client, db_session)
    resp = await client.get(endpoint, params=params, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 422, (
        f"{endpoint} with {params} returned {resp.status_code}; out-of-range "
        "pagination must be a 422 validation error, never a 500"
    )
    assert resp.json()["error"]["code"] == "validation_error"


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", _LIST_ENDPOINTS)
async def test_valid_pagination_is_accepted(
    client: AsyncClient, db_session: AsyncSession, endpoint: str
) -> None:
    token = await _admin_token(client, db_session)
    resp = await client.get(
        endpoint,
        params={"page": 1, "size": MAX_PAGE_SIZE},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", _LIST_ENDPOINTS)
async def test_pagination_defaults_apply(
    client: AsyncClient, db_session: AsyncSession, endpoint: str
) -> None:
    """Omitting the params must work — the bounds are not accidentally required."""
    token = await _admin_token(client, db_session)
    resp = await client.get(endpoint, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
