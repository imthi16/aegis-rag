"""Hash-chain unit tests (CLAUDE.md §10 — Audit DoD).

Canonicalization determinism + HMAC entry-hash properties + tamper math.
Full DB-backed verify_chain lives in tests/integration/test_audit_verify.py.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.audit.hash_chain import audit_payload, canonicalize, compute_entry_hash

GENESIS = "0" * 64


def _payload(action: str = "x") -> dict[str, object]:
    return audit_payload(
        ts=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
        actor_id=None,
        actor_roles=["admin"],
        action=action,
        resource_type="auth",
        resource_id=None,
        outcome="success",
        ip_address=None,
        request_id=uuid.UUID(int=1),
        details={"b": 2, "a": 1},
    )


def test_canonicalize_is_sorted_and_compact() -> None:
    assert canonicalize({"b": 1, "a": 2}) == b'{"a":2,"b":1}'


def test_canonicalize_key_order_independent() -> None:
    assert canonicalize({"a": 1, "b": 2}) == canonicalize({"b": 2, "a": 1})


def test_entry_hash_is_deterministic_hex64() -> None:
    p = _payload()
    h1 = compute_entry_hash(p, GENESIS, "key")
    h2 = compute_entry_hash(p, GENESIS, "key")
    assert h1 == h2
    assert len(h1) == 64
    int(h1, 16)  # valid hex


def test_entry_hash_changes_with_payload() -> None:
    assert compute_entry_hash(_payload("a"), GENESIS, "k") != compute_entry_hash(
        _payload("b"), GENESIS, "k"
    )


def test_entry_hash_changes_with_prev() -> None:
    p = _payload()
    assert compute_entry_hash(p, GENESIS, "k") != compute_entry_hash(p, "1" * 64, "k")


def test_entry_hash_changes_with_key() -> None:
    p = _payload()
    assert compute_entry_hash(p, GENESIS, "k1") != compute_entry_hash(p, GENESIS, "k2")


def test_chain_links_and_tamper_breaks_recompute() -> None:
    p1 = _payload("a")
    h1 = compute_entry_hash(p1, GENESIS, "k")
    p2 = _payload("b")
    h2 = compute_entry_hash(p2, h1, "k")

    # Tampering any field makes the recomputed hash diverge from the stored one.
    tampered = _payload("b-tampered")
    assert compute_entry_hash(tampered, h1, "k") != h2
