"""Finalize node (CLAUDE.md §6.14): citations + grounding check.

Builds citations; if the answer asserts facts but has zero citations it is
flagged unfaithful (ungrounded). Empty evidence → explicit insufficient-evidence
response (never a confident unsupported answer).
"""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.generation.citations import build_citations
from app.generation.prompts import INSUFFICIENT_EVIDENCE
from app.graph.state import GraphState


async def finalize_node(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    answer = state.get("answer", "") or ""
    reranked = state.get("reranked", [])

    if state.get("insufficient_evidence") or not reranked:
        return {
            "answer": answer or INSUFFICIENT_EVIDENCE,
            "citations": [],
            "insufficient_evidence": True,
            "faithful": False,
        }

    _, citations = build_citations(answer, reranked)
    is_insufficient = answer.strip() == INSUFFICIENT_EVIDENCE.strip()
    faithful = bool(state.get("faithful", False))

    # Factual claims but no citations → ungrounded (treat as faithfulness failure).
    if not is_insufficient and answer.strip() and not citations:
        faithful = False

    return {
        "citations": citations,
        "faithful": faithful,
        "insufficient_evidence": is_insufficient,
    }
