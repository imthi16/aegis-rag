"""Query DTOs (CLAUDE.md §7 Query)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

# Upper bound on caller-supplied top_k: a request must not be able to force an
# unbounded retrieval/rerank fan-out. Omitted → RETRIEVAL_TOP_K from config.
MAX_TOP_K = 200


class QueryRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=MAX_TOP_K)


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
