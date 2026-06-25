"""Audit DTOs (CLAUDE.md §7 Audit)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class AuditEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ts: datetime
    actor_id: uuid.UUID | None
    actor_roles: list[str]
    action: str
    resource_type: str
    resource_id: str | None
    outcome: str
    ip_address: str | None
    request_id: uuid.UUID
    details: dict[str, Any]
    prev_hash: str
    entry_hash: str

    @field_validator("ip_address", mode="before")
    @classmethod
    def _ip_to_str(cls, v: object) -> str | None:
        # asyncpg may return INET as an ipaddress object; normalize to str.
        return str(v) if v is not None else None


class AuditListResponse(BaseModel):
    items: list[AuditEntry]
    total: int
    page: int
    size: int


class ChainReport(BaseModel):
    """Result of verify_chain (§6.15)."""

    ok: bool
    total: int
    first_broken_id: int | None = None
    broken_field: str | None = None
