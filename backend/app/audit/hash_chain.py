"""Tamper-evident hash chain primitives (CLAUDE.md §6.15).

Each audit entry is HMAC-SHA256 signed over a canonical serialization of its
payload concatenated with the previous entry's hash. Canonicalization is
deterministic (sorted keys, no whitespace, UTC microsecond ISO timestamps) so
``verify_chain`` can recompute every link exactly.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime
from typing import Any

# Advisory-lock namespace used to serialize audit appends (one chain, no forks).
CHAIN_LOCK_KEY = 0x41454749  # "AEGI"


def audit_payload(
    *,
    ts: datetime,
    actor_id: uuid.UUID | None,
    actor_roles: list[str],
    action: str,
    resource_type: str,
    resource_id: str | None,
    outcome: str,
    ip_address: str | None,
    request_id: uuid.UUID | str,
    details: dict[str, Any],
) -> dict[str, Any]:
    """Build the JSON-native payload that the entry hash is computed over.

    Field set + normalization MUST match between write and verify.
    """
    return {
        "ts": ts.astimezone(UTC).isoformat(timespec="microseconds"),
        "actor_id": str(actor_id) if actor_id is not None else None,
        "actor_roles": list(actor_roles),
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "outcome": outcome,
        "ip_address": str(ip_address) if ip_address is not None else None,
        "request_id": str(request_id),
        "details": details or {},
    }


def canonicalize(entry: dict[str, Any]) -> bytes:
    """Deterministic JSON: sorted keys, no whitespace, UTF-8."""
    return json.dumps(
        entry,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def compute_entry_hash(payload: dict[str, Any], prev_hash: str, hmac_key: str) -> str:
    """entry_hash = HMAC-SHA256(key, canonical(payload) || prev_hash)."""
    body = canonicalize(payload) + prev_hash.encode("utf-8")
    return hmac.new(hmac_key.encode("utf-8"), body, hashlib.sha256).hexdigest()


def payload_from_row(row: Any) -> dict[str, Any]:
    """Reconstruct the canonical payload from a stored AuditLog row (for verify)."""
    return audit_payload(
        ts=row.ts,
        actor_id=row.actor_id,
        actor_roles=list(row.actor_roles or []),
        action=row.action,
        resource_type=row.resource_type,
        resource_id=row.resource_id,
        outcome=row.outcome,
        ip_address=str(row.ip_address) if row.ip_address is not None else None,
        request_id=row.request_id,
        details=dict(row.details or {}),
    )
