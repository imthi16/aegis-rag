"""Audit chain integration (CLAUDE.md §10 — Audit DoD).

Appends N entries → verify_chain ok; mutating a stored field makes verify report
the exact first_broken_id + broken_field.

The test schema carries the same append-only trigger as production, so an
ordinary UPDATE is impossible here too — ``_tamper`` must explicitly disable the
trigger first. That is deliberate on both counts: it asserts the guard is
actually installed (the disable/re-enable would be a no-op otherwise), and it
models the real threat the hash chain defends against — an actor with direct
database privileges who can bypass application-level controls. Defence in depth:
the trigger stops the application and ordinary roles; the chain makes tampering
by anyone else *detectable*.
"""

from __future__ import annotations

import json
import uuid

import pytest
from app.audit.logger import write_audit
from app.audit.verifier import verify_chain
from app.core.security import hash_password
from app.db.models import Role, User
from app.db.models.audit import AuditLog
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

_DISABLE_GUARD = "ALTER TABLE audit_log DISABLE TRIGGER trg_audit_log_append_only"
_ENABLE_GUARD = "ALTER TABLE audit_log ENABLE TRIGGER trg_audit_log_append_only"


async def _tamper(db: AsyncSession, target: int, **values: object) -> None:
    """Forcibly rewrite a stored audit row, bypassing the append-only trigger."""
    await db.execute(text(_DISABLE_GUARD))
    try:
        await db.execute(update(AuditLog).where(AuditLog.id == target).values(**values))
        await db.commit()
    finally:
        await db.execute(text(_ENABLE_GUARD))
        await db.commit()


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
    await _tamper(db_session, target, details={"i": 999})

    report = await verify_chain(db_session)
    assert report.ok is False
    assert report.first_broken_id == target
    assert report.broken_field == "entry_hash"


@pytest.mark.asyncio
async def test_tampered_prev_hash_detected(db_session: AsyncSession) -> None:
    ids = await _append_n(db_session, 3)
    target = ids[1]
    await _tamper(db_session, target, prev_hash="f" * 64)

    report = await verify_chain(db_session)
    assert report.ok is False
    assert report.first_broken_id == target
    assert report.broken_field == "prev_hash"


@pytest.mark.asyncio
async def test_tampered_entry_hash_detected(db_session: AsyncSession) -> None:
    ids = await _append_n(db_session, 2)
    target = ids[0]
    await _tamper(db_session, target, entry_hash="0" * 64)

    report = await verify_chain(db_session)
    assert report.ok is False
    assert report.first_broken_id == target
    assert report.broken_field == "entry_hash"


@pytest.mark.asyncio
async def test_audit_log_rejects_update(db_session: AsyncSession) -> None:
    """The append-only guard blocks UPDATE (Golden Rule 5 / §9: no mutable audit log)."""
    ids = await _append_n(db_session, 1)
    with pytest.raises(DBAPIError, match="append-only"):
        await db_session.execute(
            update(AuditLog).where(AuditLog.id == ids[0]).values(action="tampered")
        )
    await db_session.rollback()

    # The stored row is untouched.
    row = (await db_session.execute(select(AuditLog).where(AuditLog.id == ids[0]))).scalar_one()
    assert row.action == "test.event.0"


@pytest.mark.asyncio
async def test_audit_log_rejects_delete(db_session: AsyncSession) -> None:
    """The append-only guard blocks DELETE, so history cannot be pruned."""
    ids = await _append_n(db_session, 1)
    with pytest.raises(DBAPIError, match="append-only"):
        await db_session.execute(delete(AuditLog).where(AuditLog.id == ids[0]))
    await db_session.rollback()

    assert (await db_session.execute(select(func.count()).select_from(AuditLog))).scalar() == 1


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


@pytest.mark.asyncio
async def test_export_streams_jsonl(client, db_session: AsyncSession, app_sessions: None) -> None:
    """The append-only export streams one JSON object per line (§7)."""
    await _append_n(db_session, 3)
    role = Role(name="admin", description="admin")
    db_session.add(role)
    await db_session.flush()
    db_session.add(
        User(username="auditor", hashed_password=hash_password("audit-pw-123"), roles=[role])
    )
    await db_session.commit()
    tok = (
        await client.post(
            "/api/v1/auth/login", json={"username": "auditor", "password": "audit-pw-123"}
        )
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {tok}"}

    resp = await client.get("/api/v1/audit/export?format=jsonl", headers=headers)
    assert resp.status_code == 200
    lines = [json.loads(line) for line in resp.text.splitlines() if line.strip()]
    assert len(lines) >= 3
    assert {"id", "action", "entry_hash", "prev_hash"} <= set(lines[0])

    # An unsupported format must be refused, not silently served as jsonl.
    bad = await client.get("/api/v1/audit/export?format=csv", headers=headers)
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_export_does_not_leak_connections(
    client, db_session: AsyncSession, db_engine, app_sessions: None
) -> None:
    """Repeated exports must return their connections to the pool.

    Streaming from the request-scoped session leaked one connection per call:
    FastAPI finalizes yield-dependencies before a StreamingResponse body is
    consumed, so the connection was never checked back in. That exhausts the pool
    and the orphaned transactions hold locks that block DDL on audit_log.
    """
    await _append_n(db_session, 2)
    role = Role(name="admin", description="admin")
    db_session.add(role)
    await db_session.flush()
    db_session.add(
        User(username="leakcheck", hashed_password=hash_password("leak-pw-123"), roles=[role])
    )
    await db_session.commit()
    tok = (
        await client.post(
            "/api/v1/auth/login", json={"username": "leakcheck", "password": "leak-pw-123"}
        )
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {tok}"}

    for _ in range(5):
        resp = await client.get("/api/v1/audit/export", headers=headers)
        assert resp.status_code == 200
        assert resp.text.strip(), "export produced no rows"

    # A leaked session leaves its backend parked inside a transaction.
    async with db_engine.connect() as conn:
        stranded = (
            await conn.execute(
                text(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE datname = current_database() "
                    "AND pid <> pg_backend_pid() "
                    "AND state = 'idle in transaction'"
                )
            )
        ).scalar_one()
    assert stranded == 0, f"{stranded} backend(s) stranded in a transaction after exports"

    # The consequence that actually bites: an orphaned transaction holds locks
    # that block DDL on audit_log, i.e. migrations.
    async with db_engine.begin() as conn:
        await conn.execute(text("SET LOCAL lock_timeout='5s'"))
        await conn.execute(text("ALTER TABLE audit_log ADD COLUMN _probe integer"))
        await conn.execute(text("ALTER TABLE audit_log DROP COLUMN _probe"))
