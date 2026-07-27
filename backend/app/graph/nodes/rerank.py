"""Rerank node (CLAUDE.md §6.14): cross-encoder rerank → top_n."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.core.config import get_settings
from app.graph.state import GraphState
from app.retrieval.reranker import get_reranker


async def rerank_node(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    candidates = state.get("candidates", [])
    if not candidates:
        return {"reranked": []}
    settings = get_settings()
    reranked = get_reranker().rerank(state["query"], candidates, settings.rerank_top_n)
    return {"reranked": reranked}
