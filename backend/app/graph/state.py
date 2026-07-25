"""LangGraph state (CLAUDE.md §6.13).

Threaded through the nodes. Per-request dependencies (db session, User, request
id) are passed via the RunnableConfig ``configurable`` rather than the state, so
the state stays a plain data object.
"""

from __future__ import annotations

from typing import Any, TypedDict

from app.generation.citations import Citation
from app.retrieval.hybrid import Candidate


class GraphState(TypedDict, total=False):
    query: str
    user_id: str
    user_roles: list[str]
    top_k: int  # per-channel candidates before fusion; defaults to RETRIEVAL_TOP_K
    candidates: list[Candidate]  # post-hybrid
    reranked: list[Candidate]  # post-rerank, fed to generation
    doc_grades: list[dict[str, Any]]  # CRAG per-doc {chunk_id, relevant, score}
    needs_correction: bool
    correction_attempts: int
    answer: str
    citations: list[Citation]
    faithfulness_score: float
    faithful: bool
    regen_attempts: int
    insufficient_evidence: bool
    audit_request_id: str
