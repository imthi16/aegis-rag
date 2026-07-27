"""Retrieve node (CLAUDE.md §6.14): hybrid_retrieve → candidates."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.core.config import get_settings
from app.graph.nodes import get_deps
from app.graph.state import GraphState
from app.retrieval.hybrid import hybrid_retrieve


async def retrieve_node(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    deps = get_deps(config)
    settings = get_settings()
    # Caller-supplied top_k (validated at the API boundary) overrides the default.
    top_k = state.get("top_k") or settings.retrieval_top_k
    candidates = await hybrid_retrieve(deps.db, query=state["query"], user=deps.user, top_k=top_k)
    return {"candidates": candidates, "insufficient_evidence": len(candidates) == 0}
