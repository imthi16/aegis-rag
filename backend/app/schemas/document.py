"""Document DTOs (CLAUDE.md §7 Documents)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class DocumentSummary(BaseModel):
    id: uuid.UUID
    filename: str
    classification: str
    allowed_roles: list[str]
    chunk_count: int
    status: str
    page_count: int | None
    created_at: datetime


class DocumentDetail(DocumentSummary):
    content_hash: str
    filetype: str
    uploaded_by: uuid.UUID | None
    metadata: dict[str, Any]


class UploadResponse(BaseModel):
    id: uuid.UUID
    filename: str
    classification: str
    allowed_roles: list[str]
    chunk_count: int
    status: str


class DocumentListResponse(BaseModel):
    items: list[DocumentSummary]
    total: int
    page: int
    size: int


class DeleteResponse(BaseModel):
    status: str = "deleted"


class ReindexResponse(BaseModel):
    status: str = "reindexing"
