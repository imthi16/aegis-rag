"""Reranker unit tests (CLAUDE.md §10 — Hybrid + reranker DoD).

The pure rerank_by_scores helper reorders by score and truncates to top_n
(testable without the model weights).
"""

from __future__ import annotations

import uuid

from app.retrieval.hybrid import Candidate
from app.retrieval.reranker import rerank_by_scores


def _cand(content: str) -> Candidate:
    return Candidate(
        faiss_id=abs(hash(content)) & 0x7FFFFFFF,
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        content=content,
        char_start=0,
        char_end=len(content),
        page_number=1,
        score=0.0,
    )


def test_rerank_reorders_and_truncates() -> None:
    cands = [_cand("a"), _cand("b"), _cand("c")]
    out = rerank_by_scores(cands, [0.1, 0.9, 0.5], top_n=2)
    assert [c.content for c in out] == ["b", "c"]
    assert out[0].score == 0.9
    assert len(out) == 2


def test_rerank_empty() -> None:
    assert rerank_by_scores([], [], top_n=5) == []
