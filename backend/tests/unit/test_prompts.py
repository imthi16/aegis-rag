"""Prompt template unit tests (CLAUDE.md §10 — Generation DoD)."""

from __future__ import annotations

import uuid

from app.generation.prompts import (
    INSUFFICIENT_EVIDENCE,
    doc_relevance_prompt,
    faithfulness_prompt,
    generation_prompt,
    query_rewrite_prompt,
)
from app.retrieval.hybrid import Candidate


def _ctx(content: str) -> Candidate:
    return Candidate(
        faiss_id=1,
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        content=content,
        char_start=0,
        char_end=len(content),
        page_number=1,
        score=0.0,
    )


def test_generation_prompt_numbers_contexts_and_demands_citations() -> None:
    msgs = generation_prompt("What is X?", [_ctx("first"), _ctx("second")])
    assert msgs[0]["role"] == "system"
    assert "ONLY" in msgs[0]["content"]
    assert INSUFFICIENT_EVIDENCE in msgs[0]["content"]
    user = msgs[1]["content"]
    assert "[1] first" in user
    assert "[2] second" in user
    assert "What is X?" in user


def test_grading_prompts_force_json() -> None:
    assert "JSON" in doc_relevance_prompt("q", "ctx")[0]["content"]
    assert "JSON" in faithfulness_prompt("a", [_ctx("c")])[0]["content"]


def test_query_rewrite_prompt_is_query_only() -> None:
    msgs = query_rewrite_prompt("original", "no relevant docs")
    assert "rewrite" in msgs[0]["content"].lower()
    assert "original" in msgs[1]["content"]
