"""Audit chain integration (CLAUDE.md §10 — Audit DoD).

Appends N entries → verify_chain ok; mutating a stored field makes verify report
the exact first_broken_id + broken_field. Uses the create_all schema (no
append-only trigger) so the tamper UPDATE is possible for the test.
"""

from __future__ import annotations

import uuid

import pytest
from app.audit.logger import write_audit
from app.audit.verifier import verify_chain
from app.db.models.audit import AuditLog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession


async def _append_n(db: AsyncSession, n: int) -> list[int]:
    ids: list[int] = []
    for i in range(n):
        row = await write_audit(
            db,
            actor_id=None,
            actor_roles=["admin"],
            action=f"test.event.{i}",
            resource_type="test",
            resource_id=str(i),
            outcome="success",
            ip=None,
            request_id=str(uuid.uuid4()),
            details={"i": i},
        )
        ids.append(row.id)
    await db.commit()
    return ids


@pytest.mark.asyncio
async def test_intact_chain_verifies(db_session: AsyncSession) -> None:
    await _append_n(db_session, 5)
    report = await verify_chain(db_session)
    assert report.ok is True
    assert report.total == 5
    assert report.first_broken_id is None
    assert report.broken_field is None


@pytest.mark.asyncio
async def test_empty_chain_is_ok(db_session: AsyncSession) -> None:
    report = await verify_chain(db_session)
    assert report.ok is True
    assert report.total == 0


@pytest.mark.asyncio
async def test_tampered_details_detected(db_session: AsyncSession) -> None:
    ids = await _append_n(db_session, 3)
    target = ids[1]
    await db_session.execute(
        update(AuditLog).where(AuditLog.id == target).values(details={"i": 999})
    )
    await db_session.commit()

    report = await verify_chain(db_session)
    assert report.ok is False
    assert report.first_broken_id == target
    assert report.broken_field == "entry_hash"


@pytest.mark.asyncio
async def test_tampered_prev_hash_detected(db_session: AsyncSession) -> None:
    ids = await _append_n(db_session, 3)
    target = ids[1]
    await db_session.execute(
        update(AuditLog).where(AuditLog.id == target).values(prev_hash="f" * 64)
    )
    await db_session.commit()

    report = await verify_chain(db_session)
    assert report.ok is False
    assert report.first_broken_id == target
    assert report.broken_field == "prev_hash"


@pytest.mark.asyncio
async def test_tampered_entry_hash_detected(db_session: AsyncSession) -> None:
    ids = await _append_n(db_session, 2)
    target = ids[0]
    await db_session.execute(
        update(AuditLog).where(AuditLog.id == target).values(entry_hash="0" * 64)
    )
    await db_session.commit()

    report = await verify_chain(db_session)
    assert report.ok is False
    assert report.first_broken_id == target
    assert report.broken_field == "entry_hash"


@pytest.mark.asyncio
async def test_login_writes_audit_record(client, db_session: AsyncSession) -> None:
    """Wiring smoke: a failed login appends an auth.login_failed audit row."""
    resp = await client.post("/api/v1/auth/login", json={"username": "nobody", "password": "x"})
    assert resp.status_code == 401
    rows = (
        (await db_session.execute(select(AuditLog).where(AuditLog.action == "auth.login_failed")))
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].outcome == "denied"
