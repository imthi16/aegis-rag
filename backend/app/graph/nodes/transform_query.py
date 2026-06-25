"""Corrective query rewrite (CLAUDE.md §6.14).

Internal rewrite + re-retrieval only — NEVER a web search (Golden Rule 4).
"""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.core.config import get_settings
from app.generation.llm import get_llm
from app.generation.prompts import query_rewrite_prompt
from app.graph.state import GraphState


async def transform_query_node(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    settings = get_settings()
    llm = get_llm()
    attempts = state.get("correction_attempts", 0) + 1
    rewritten = (
        await llm.chat(
            query_rewrite_prompt(state["query"], "low document relevance"),
            temperature=settings.ollama_temperature_grade,
            num_ctx=settings.ollama_num_ctx,
        )
    ).strip()
    return {
        "query": rewritten or state["query"],
        "correction_attempts": attempts,
    }
