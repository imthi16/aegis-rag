"""CRAG document-relevance grading (CLAUDE.md §6.14).

Grades each reranked doc (JSON, temperature 0); flags needs_correction when the
mean score is below threshold OR too few docs are relevant; drops irrelevant
docs from ``reranked``.
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.runnables import RunnableConfig

from app.core.config import get_settings
from app.generation.llm import get_llm
from app.generation.prompts import doc_relevance_prompt
from app.graph.state import GraphState


async def grade_documents_node(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    settings = get_settings()
    llm = get_llm()
    reranked = state.get("reranked", [])

    grades: list[dict[str, Any]] = []
    relevant = []
    for cand in reranked:
        raw = await llm.chat(
            doc_relevance_prompt(state["query"], cand.content),
            temperature=settings.ollama_temperature_grade,
            num_ctx=settings.ollama_num_ctx,
            format="json",
        )
        try:
            data = json.loads(raw)
            is_relevant = bool(data.get("relevant", False))
            score = float(data.get("score", 0.0))
        except (json.JSONDecodeError, ValueError, TypeError):
            is_relevant, score = False, 0.0
        grades.append({"chunk_id": str(cand.chunk_id), "relevant": is_relevant, "score": score})
        if is_relevant:
            relevant.append(cand)

    mean_score = sum(g["score"] for g in grades) / len(grades) if grades else 0.0
    needs_correction = (mean_score < settings.crag_relevance_threshold) or (
        len(relevant) < settings.crag_min_relevant_docs
    )
    return {
        "doc_grades": grades,
        "needs_correction": needs_correction,
        "reranked": relevant,
    }
