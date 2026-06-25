"""Faithfulness grading (CLAUDE.md §6.14): JSON verdict, temperature 0."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.runnables import RunnableConfig

from app.core.config import get_settings
from app.generation.llm import get_llm
from app.generation.prompts import faithfulness_prompt
from app.graph.state import GraphState


async def grade_faithfulness_node(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    settings = get_settings()
    llm = get_llm()
    raw = await llm.chat(
        faithfulness_prompt(state.get("answer", ""), state.get("reranked", [])),
        temperature=settings.ollama_temperature_grade,
        num_ctx=settings.ollama_num_ctx,
        format="json",
    )
    try:
        data = json.loads(raw)
        score = float(data.get("score", 0.0))
    except (json.JSONDecodeError, ValueError, TypeError):
        score = 0.0
    # Deterministic verdict from the score (don't trust the model's own bool).
    return {"faithfulness_score": score, "faithful": score >= settings.faithfulness_threshold}
