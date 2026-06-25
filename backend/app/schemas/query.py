"""Query DTOs (CLAUDE.md §7 Query)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel


class QueryRequest(BaseModel):
    query: str
    top_k: int | None = None


class CitationOut(BaseModel):
    marker: int
    document_id: uuid.UUID
    chunk_id: uuid.UUID
    page_number: int | None
    char_start: int
    char_end: int
    snippet: str


class RetrievedChunk(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    score: float
    page_number: int | None
    content_preview: str


class DocGrade(BaseModel):
    chunk_id: uuid.UUID
    relevant: bool
    score: float


class QueryResponse(BaseModel):
    answer: str
    insufficient_evidence: bool
    faithful: bool
    faithfulness_score: float
    citations: list[CitationOut]
    retrieved_chunks: list[RetrievedChunk]
    doc_grades: list[DocGrade]
    correction_applied: bool
    latency_ms: int
    request_id: str
