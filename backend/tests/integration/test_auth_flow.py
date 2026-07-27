"""Auth flow integration (CLAUDE.md §10 — Auth + RBAC DoD).

Login returns access+refresh; bad credentials → 401; /me reflects identity;
refresh rotates + revokes; an expired/invalid token → 401. Skips without a DB.
"""

from __future__ import annotations

import pytest
from app.core.security import hash_password
from app.db.models import Role, User
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


async def _make_user(db: AsyncSession, username: str, password: str, role: str) -> None:
    r = Role(name=role, description=role)
    db.add(r)
    await db.flush()
    db.add(
        User(
            username=username,
            hashed_password=hash_password(password),
            is_active=True,
            roles=[r],
        )
    )
    await db.commit()


@pytest.mark.asyncio
async def test_login_success_and_me(client: AsyncClient, db_session: AsyncSession) -> None:
    await _make_user(db_session, "alice", "s3cret-pass", "analyst")

    resp = await client.post(
        "/api/v1/auth/login", json={"username": "alice", "password": "s3cret-pass"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["username"] == "alice"
    assert body["user"]["roles"] == ["analyst"]
    access = body["access_token"]

    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 200
    assert me.json()["username"] == "alice"
    assert me.json()["is_active"] is True


@pytest.mark.asyncio
async def test_login_bad_password_is_401(client: AsyncClient, db_session: AsyncSession) -> None:
    await _make_user(db_session, "bob", "right-pass", "viewer")
    resp = await client.post("/api/v1/auth/login", json={"username": "bob", "password": "wrong"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_unknown_user_is_401(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/auth/login", json={"username": "ghost", "password": "x"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_missing_token_is_401(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] in {"invalid_token", "unauthorized"}


@pytest.mark.asyncio
async def test_refresh_rotates_and_revokes(client: AsyncClient, db_session: AsyncSession) -> None:
    await _make_user(db_session, "carol", "pw-12345", "viewer")
    login = await client.post(
        "/api/v1/auth/login", json={"username": "carol", "password": "pw-12345"}
    )
    refresh_token = login.json()["refresh_token"]

    first = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert first.status_code == 200
    assert first.json()["access_token"]

    # The old refresh token was revoked on rotation → reuse fails.
    reuse = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert reuse.status_code == 401


@pytest.mark.asyncio
async def test_garbage_token_is_401(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401
