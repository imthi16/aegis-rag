"""Generation node (CLAUDE.md §6.14): grounded answer over reranked contexts."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.core.config import get_settings
from app.generation.llm import get_llm
from app.generation.prompts import generation_prompt
from app.graph.state import GraphState


async def generate_node(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    settings = get_settings()
    llm = get_llm()
    # Count a regeneration (re-entry after a faithfulness failure).
    attempts = state.get("regen_attempts", 0)
    if state.get("answer"):
        attempts += 1
    answer = await llm.chat(
        generation_prompt(state["query"], state.get("reranked", [])),
        temperature=settings.ollama_temperature_gen,
        num_ctx=settings.ollama_num_ctx,
    )
    return {"answer": answer, "regen_attempts": attempts}
