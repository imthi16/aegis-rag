"""Audit append logger (CLAUDE.md §6.15).

``write_audit`` appends one hash-chained, HMAC-signed row. It runs inside the
caller's transaction and serializes appends with a Postgres advisory lock so the
chain never forks. It only flushes — the caller commits, making the audit record
atomic with the triggering operation (fail closed: if the audit append raises,
the whole transaction rolls back).

Append-only immutability is additionally enforced at the DB layer by the
BEFORE UPDATE/DELETE trigger on ``audit_log`` (migration 0001), which blocks
mutation for every role. The least-privilege ``aegis_audit`` role (INSERT/SELECT
only) is provisioned for out-of-band audit access.
"""

from __future__ import annotations

import ipaddress
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.hash_chain import (
    CHAIN_LOCK_KEY,
    audit_payload,
    compute_entry_hash,
)
from app.core.config import get_settings
from app.core.exceptions import AuditIntegrityError
from app.core.logging import get_logger
from app.db.models.audit import AuditLog

logger = get_logger("app.audit")

Outcome = Literal["success", "denied", "error"]


def _sanitize_ip(ip: str | None) -> str | None:
    if not ip:
        return None
    try:
        ipaddress.ip_address(ip)
        return ip
    except ValueError:
        return None


async def write_audit(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
    actor_roles: list[str],
    action: str,
    resource_type: str,
    resource_id: str | None,
    outcome: Outcome,
    ip: str | None,
    request_id: str,
    details: dict[str, Any],
) -> AuditLog:
    settings = get_settings()
    try:
        # Serialize all audit appends so the chain is linear (no forks).
        await db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": CHAIN_LOCK_KEY})

        prev = (
            await db.execute(select(AuditLog.entry_hash).order_by(AuditLog.id.desc()).limit(1))
        ).scalar_one_or_none()
        prev_hash = prev if prev is not None else settings.audit_chain_genesis_hash

        ts = datetime.now(UTC)
        clean_ip = _sanitize_ip(ip)
        req_uuid = uuid.UUID(str(request_id))

        payload = audit_payload(
            ts=ts,
            actor_id=actor_id,
            actor_roles=actor_roles,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            outcome=outcome,
            ip_address=clean_ip,
            request_id=req_uuid,
            details=details,
        )
        entry_hash = compute_entry_hash(payload, prev_hash, settings.audit_hmac_key)

        row = AuditLog(
            ts=ts,
            actor_id=actor_id,
            actor_roles=list(actor_roles),
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            outcome=outcome,
            ip_address=clean_ip,
            request_id=req_uuid,
            details=details or {},
            prev_hash=prev_hash,
            entry_hash=entry_hash,
        )
        db.add(row)
        await db.flush()
        return row
    except Exception as exc:
        # Fail closed: the triggering operation must not proceed.
        logger.error("audit_write_failed", action=action, error_type=type(exc).__name__)
        raise AuditIntegrityError("Failed to append audit record.") from exc
