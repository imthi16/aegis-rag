"""Audit routes (CLAUDE.md §7 Audit). Roles: compliance_auditor, admin.

GET /audit         — paginated, filterable list.
GET /audit/verify  — full-chain integrity check (audited as audit.verified).
GET /audit/export  — append-only JSONL export.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.logger import Outcome, write_audit
from app.audit.verifier import verify_chain
from app.core.dependencies import get_db, require_roles
from app.db.models.audit import AuditLog
from app.db.models.user import User
from app.rbac.classifications import Role
from app.schemas.audit import AuditEntry, AuditListResponse, ChainReport

router = APIRouter(prefix="/audit", tags=["audit"])

_auditor = require_roles(Role.COMPLIANCE_AUDITOR, Role.ADMIN)


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _build_filters(
    actor_id: uuid.UUID | None,
    action: str | None,
    from_: datetime | None,
    to: datetime | None,
) -> list[Any]:
    filters: list[Any] = []
    if actor_id is not None:
        filters.append(AuditLog.actor_id == actor_id)
    if action:
        filters.append(AuditLog.action == action)
    if from_ is not None:
        filters.append(AuditLog.ts >= from_)
    if to is not None:
        filters.append(AuditLog.ts <= to)
    return filters


@router.get("", response_model=AuditListResponse)
async def list_audit(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    actor_id: uuid.UUID | None = None,
    action: str | None = None,
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = None,
    user: User = Depends(_auditor),
    db: AsyncSession = Depends(get_db),
) -> AuditListResponse:
    filters = _build_filters(actor_id, action, from_, to)

    count_stmt = select(func.count()).select_from(AuditLog)
    list_stmt = select(AuditLog).order_by(AuditLog.id.desc())
    if filters:
        cond = and_(*filters)
        count_stmt = count_stmt.where(cond)
        list_stmt = list_stmt.where(cond)

    total = (await db.execute(count_stmt)).scalar_one()
    rows = (await db.execute(list_stmt.offset((page - 1) * size).limit(size))).scalars().all()
    return AuditListResponse(
        items=[AuditEntry.model_validate(r) for r in rows],
        total=total,
        page=page,
        size=size,
    )


@router.get("/verify", response_model=ChainReport)
async def verify(
    request: Request,
    start_id: int = 0,
    user: User = Depends(_auditor),
    db: AsyncSession = Depends(get_db),
) -> ChainReport:
    report = await verify_chain(db, start_id=start_id)
    outcome: Outcome = "success" if report.ok else "error"
    await write_audit(
        db,
        actor_id=user.id,
        actor_roles=user.role_names,
        action="audit.verified",
        resource_type="audit",
        resource_id=None,
        outcome=outcome,
        ip=_client_ip(request),
        request_id=str(request.state.request_id),
        details={
            "start_id": start_id,
            "ok": report.ok,
            "first_broken_id": report.first_broken_id,
        },
    )
    await db.commit()
    return report


@router.get("/export")
async def export(
    fmt: str = Query("jsonl", alias="format"),
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = None,
    user: User = Depends(_auditor),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    filters = _build_filters(None, None, from_, to)
    stmt = select(AuditLog).order_by(AuditLog.id.asc())
    if filters:
        stmt = stmt.where(and_(*filters))

    async def _gen() -> AsyncIterator[str]:
        result = await db.stream(stmt)
        async for row in result.scalars():
            yield AuditEntry.model_validate(row).model_dump_json() + "\n"

    return StreamingResponse(
        _gen(),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": "attachment; filename=audit-export.jsonl"},
    )
