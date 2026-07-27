"""LangGraph wiring (CLAUDE.md §6.14).

retrieve → rerank → grade_documents (CRAG) → [transform_query → retrieve] →
generate → grade_faithfulness → [regen] → finalize. Routers terminate by
respecting MAX_CORRECTION_ATTEMPTS / MAX_REGEN_ATTEMPTS.
"""

from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.core.config import get_settings
from app.graph.nodes.finalize import finalize_node
from app.graph.nodes.generate import generate_node
from app.graph.nodes.grade_documents import grade_documents_node
from app.graph.nodes.grade_faithfulness import grade_faithfulness_node
from app.graph.nodes.rerank import rerank_node
from app.graph.nodes.retrieve import retrieve_node
from app.graph.nodes.transform_query import transform_query_node
from app.graph.state import GraphState


def route_after_retrieve(state: GraphState) -> str:
    return "empty" if state.get("insufficient_evidence") else "ok"


def route_after_crag(state: GraphState) -> str:
    settings = get_settings()
    if state.get("needs_correction") and state.get("correction_attempts", 0) < (
        settings.max_correction_attempts
    ):
        return "correct"
    return "generate"


def route_after_transform(state: GraphState) -> str:
    settings = get_settings()
    if state.get("correction_attempts", 0) <= settings.max_correction_attempts:
        return "retry"
    return "giveup"


def route_after_faithfulness(state: GraphState) -> str:
    settings = get_settings()
    if not state.get("faithful", False) and state.get("regen_attempts", 0) < (
        settings.max_regen_attempts
    ):
        return "regen"
    return "done"


def build_graph() -> CompiledStateGraph:
    g = StateGraph(GraphState)
    g.add_node("retrieve", retrieve_node)
    g.add_node("rerank", rerank_node)
    g.add_node("grade_documents", grade_documents_node)
    g.add_node("transform_query", transform_query_node)
    g.add_node("generate", generate_node)
    g.add_node("grade_faithfulness", grade_faithfulness_node)
    g.add_node("finalize", finalize_node)

    g.add_edge(START, "retrieve")
    g.add_conditional_edges("retrieve", route_after_retrieve, {"empty": "finalize", "ok": "rerank"})
    g.add_edge("rerank", "grade_documents")
    g.add_conditional_edges(
        "grade_documents",
        route_after_crag,
        {"correct": "transform_query", "generate": "generate"},
    )
    g.add_conditional_edges(
        "transform_query",
        route_after_transform,
        {"retry": "retrieve", "giveup": "generate"},
    )
    g.add_edge("generate", "grade_faithfulness")
    g.add_conditional_edges(
        "grade_faithfulness",
        route_after_faithfulness,
        {"regen": "generate", "done": "finalize"},
    )
    g.add_edge("finalize", END)
    return g.compile()


@lru_cache
def get_graph() -> CompiledStateGraph:
    return build_graph()
