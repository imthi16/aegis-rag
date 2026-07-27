"""Admin/RBAC route integration (CLAUDE.md §7 Admin).

Admin can create users + roles and assign/revoke roles (audited); non-admins are
blocked (403).
"""

from __future__ import annotations

import pytest
from app.core.security import hash_password
from app.db.models import AuditLog, Role, User
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def _user(db: AsyncSession, username: str, password: str, role: str) -> None:
    r = (await db.execute(select(Role).where(Role.name == role))).scalar_one_or_none()
    if r is None:
        r = Role(name=role, description=role)
        db.add(r)
        await db.flush()
    db.add(User(username=username, hashed_password=hash_password(password), roles=[r]))
    await db.commit()


async def _token(client: AsyncClient, username: str, password: str) -> str:
    resp = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 200
    return str(resp.json()["access_token"])


@pytest.mark.asyncio
async def test_admin_creates_user_and_assigns_roles(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    pw = "admin-pass-123"
    await _user(db_session, "root", pw, "admin")
    # Pre-create the roles the admin will reference.
    for name in ("viewer", "analyst"):
        db_session.add(Role(name=name, description=name))
    await db_session.commit()

    headers = {"Authorization": f"Bearer {await _token(client, 'root', pw)}"}

    created = await client.post(
        "/api/v1/admin/users",
        json={"username": "newbie", "email": "n@a.b", "password": "x" * 10, "roles": ["viewer"]},
        headers=headers,
    )
    assert created.status_code == 201
    user_id = created.json()["id"]
    assert created.json()["roles"] == ["viewer"]

    # Assign analyst, revoke viewer.
    updated = await client.post(
        f"/api/v1/admin/users/{user_id}/roles",
        json={"add": ["analyst"], "remove": ["viewer"]},
        headers=headers,
    )
    assert updated.status_code == 200
    assert set(updated.json()["roles"]) == {"analyst"}

    # role.assigned + role.revoked were audited.
    actions = {
        a.action
        for a in (await db_session.execute(select(AuditLog))).scalars().all()
        if a.resource_id == user_id
    }
    assert {"role.assigned", "role.revoked"} <= actions


@pytest.mark.asyncio
async def test_non_admin_cannot_access_admin_routes(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    pw = "viewer-pass-1"
    await _user(db_session, "vw", pw, "viewer")
    headers = {"Authorization": f"Bearer {await _token(client, 'vw', pw)}"}
    resp = await client.get("/api/v1/admin/users", headers=headers)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"


@pytest.mark.asyncio
async def test_admin_creates_role(client: AsyncClient, db_session: AsyncSession) -> None:
    pw = "admin-pass-123"
    await _user(db_session, "root", pw, "admin")
    headers = {"Authorization": f"Bearer {await _token(client, 'root', pw)}"}
    resp = await client.post(
        "/api/v1/admin/roles",
        json={"name": "compliance_auditor", "description": "auditor"},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "compliance_auditor"


@pytest.mark.asyncio
async def test_cannot_remove_the_last_admin_role(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Demoting the only admin would make access-control administration impossible.

    §11 requires auditable admin role separation (DIFC Reg 10 / FINMA); with zero
    admins left, roles and documents can only be managed via direct DB access.
    Fail closed and record the denial.
    """
    pw = "admin-pass-123"
    await _user(db_session, "root", pw, "admin")
    headers = {"Authorization": f"Bearer {await _token(client, 'root', pw)}"}

    me = await client.get("/api/v1/auth/me", headers=headers)
    admin_id = me.json()["id"]

    resp = await client.post(
        f"/api/v1/admin/users/{admin_id}/roles",
        json={"add": [], "remove": ["admin"]},
        headers=headers,
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"

    # Still an admin.
    still = await client.get("/api/v1/auth/me", headers=headers)
    assert "admin" in still.json()["roles"]

    # The refusal is auditable.
    denied = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "role.revoked", AuditLog.outcome == "denied"
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(denied) == 1
    assert denied[0].details["reason"] == "last_admin"


@pytest.mark.asyncio
async def test_can_remove_admin_when_another_admin_remains(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The guard protects the *last* admin only — it must not block normal demotion."""
    pw = "admin-pass-123"
    await _user(db_session, "root", pw, "admin")
    headers = {"Authorization": f"Bearer {await _token(client, 'root', pw)}"}

    created = await client.post(
        "/api/v1/admin/users",
        json={
            "username": "second",
            "email": "second@example.com",
            "password": "second-pass-123",
            "roles": ["admin"],
        },
        headers=headers,
    )
    assert created.status_code == 201
    second_id = created.json()["id"]

    resp = await client.post(
        f"/api/v1/admin/users/{second_id}/roles",
        json={"add": [], "remove": ["admin"]},
        headers=headers,
    )
    assert resp.status_code == 200
    assert "admin" not in resp.json()["roles"]
