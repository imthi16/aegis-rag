"""Full-chain integrity verification (CLAUDE.md §6.15).

Recomputes each entry hash and checks linkage sequentially, reporting the first
broken id and which field broke (``entry_hash`` for a tampered payload/hash,
``prev_hash`` for a broken/forged link or a deleted row).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.hash_chain import compute_entry_hash, payload_from_row
from app.core.config import get_settings
from app.db.models.audit import AuditLog
from app.schemas.audit import ChainReport


async def verify_chain(db: AsyncSession, start_id: int = 0) -> ChainReport:
    settings = get_settings()
    rows = (
        (
            await db.execute(
                select(AuditLog).where(AuditLog.id > start_id).order_by(AuditLog.id.asc())
            )
        )
        .scalars()
        .all()
    )
    total = len(rows)
    prev_entry_hash: str | None = None

    for idx, row in enumerate(rows):
        # 1) Linkage.
        if idx == 0:
            # Verifying from the beginning anchors on the genesis hash.
            if start_id == 0 and row.prev_hash != settings.audit_chain_genesis_hash:
                return ChainReport(
                    ok=False, total=total, first_broken_id=row.id, broken_field="prev_hash"
                )
        elif row.prev_hash != prev_entry_hash:
            return ChainReport(
                ok=False, total=total, first_broken_id=row.id, broken_field="prev_hash"
            )

        # 2) Entry hash (covers every payload field + prev_hash).
        recomputed = compute_entry_hash(
            payload_from_row(row), row.prev_hash, settings.audit_hmac_key
        )
        if recomputed != row.entry_hash:
            return ChainReport(
                ok=False, total=total, first_broken_id=row.id, broken_field="entry_hash"
            )

        prev_entry_hash = row.entry_hash

    return ChainReport(ok=True, total=total, first_broken_id=None, broken_field=None)
