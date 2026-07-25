"""Query routes (CLAUDE.md §7 Query).

POST /query        → QueryResponse
POST /query/stream → SSE tokens then a final `event: done` with QueryResponse

Each query drives the compiled LangGraph and writes one query_log row + one
query.executed audit record.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from typing import Any, cast

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from langchain_core.runnables import RunnableConfig
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.logger import write_audit
from app.core.dependencies import get_current_user, get_db
from app.db.models.query_log import QueryLog
from app.db.models.user import User
from app.graph.pipeline import get_graph
from app.graph.state import GraphState
from app.rbac.enforcement import allowed_document_ids
from app.schemas.query import (
    CitationOut,
    DocGrade,
    QueryRequest,
    QueryResponse,
    RetrievedChunk,
)

router = APIRouter(prefix="/query", tags=["query"])

_PREVIEW = 200


async def _run_query(
    db: AsyncSession,
    user: User,
    request: Request,
    query_text: str,
    top_k: int | None = None,
) -> QueryResponse:
    t0 = time.perf_counter()
    rid = str(request.state.request_id)

    # RBAC visibility is computed here purely to classify the audit outcome. The
    # response contract is unchanged (§6.9: an empty allowed set yields an
    # explicit insufficient-evidence answer, never an error), but a query that
    # could reach no content at all is recorded as ``query.denied`` rather than
    # ``query.executed`` (§6.15 audited actions).
    has_visible_documents = bool(await allowed_document_ids(db, user))

    initial: GraphState = {
        "query": query_text,
        "user_id": str(user.id),
        "user_roles": user.role_names,
        "correction_attempts": 0,
        "regen_attempts": 0,
        "audit_request_id": rid,
    }
    if top_k is not None:
        initial["top_k"] = top_k
    config: RunnableConfig = {
        "configurable": {"db": db, "user": user, "request_id": rid},
        "recursion_limit": 25,
    }
    final = cast(dict[str, Any], await get_graph().ainvoke(initial, config=config))
    latency_ms = int((time.perf_counter() - t0) * 1000)

    reranked = final.get("reranked", [])
    answer = final.get("answer", "") or ""
    insufficient = bool(final.get("insufficient_evidence", False))
    faithful = bool(final.get("faithful", False))
    score = float(final.get("faithfulness_score", 0.0))
    correction_applied = int(final.get("correction_attempts", 0)) > 0

    citations = [
        CitationOut(
            marker=c.marker,
            document_id=c.document_id,
            chunk_id=c.chunk_id,
            page_number=c.page_number,
            char_start=c.char_start,
            char_end=c.char_end,
            snippet=c.snippet,
        )
        for c in final.get("citations", [])
    ]
    retrieved = [
        RetrievedChunk(
            chunk_id=c.chunk_id,
            document_id=c.document_id,
            score=c.score,
            page_number=c.page_number,
            content_preview=c.content[:_PREVIEW],
        )
        for c in reranked
    ]
    doc_grades = [
        DocGrade(chunk_id=uuid.UUID(g["chunk_id"]), relevant=g["relevant"], score=g["score"])
        for g in final.get("doc_grades", [])
    ]

    query_log = QueryLog(
        user_id=user.id,
        query_text=query_text,
        retrieved_chunk_ids=[c.chunk_id for c in reranked],
        answer_text=answer,
        citations=[c.model_dump(mode="json") for c in citations],
        faithfulness_score=round(score, 3),
        faithful=faithful,
        insufficient_evidence=insufficient,
        correction_applied=correction_applied,
        latency_ms=latency_ms,
    )
    db.add(query_log)
    await db.flush()

    await write_audit(
        db,
        actor_id=user.id,
        actor_roles=user.role_names,
        action="query.executed" if has_visible_documents else "query.denied",
        resource_type="query",
        resource_id=str(query_log.id),
        outcome="success" if has_visible_documents else "denied",
        ip=request.client.host if request.client else None,
        request_id=rid,
        details={
            "insufficient_evidence": insufficient,
            "faithful": faithful,
            "correction_applied": correction_applied,
            **({} if has_visible_documents else {"reason": "no_accessible_documents"}),
        },
    )
    await db.commit()

    return QueryResponse(
        answer=answer,
        insufficient_evidence=insufficient,
        faithful=faithful,
        faithfulness_score=score,
        citations=citations,
        retrieved_chunks=retrieved,
        doc_grades=doc_grades,
        correction_applied=correction_applied,
        latency_ms=latency_ms,
        request_id=rid,
    )


@router.post("", response_model=QueryResponse)
async def query(
    body: QueryRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QueryResponse:
    return await _run_query(db, user, request, body.query, body.top_k)


def _sse_frame(data: str, event: str | None = None) -> str:
    """Encode one SSE frame, splitting embedded newlines across ``data:`` lines.

    Emits the single space after ``data:`` that the SSE grammar defines as a
    delimiter, because consumers strip exactly one — so a payload that itself
    begins with a space survives the round trip. (Omitting it would make the
    first payload space indistinguishable from the delimiter.) Splitting on
    newlines is what preserves them: the previous implementation appended a space
    to every token and dropped line structure from what the user saw.
    """
    lines = "".join(f"data: {line}\n" for line in data.split("\n"))
    prefix = f"event: {event}\n" if event else ""
    return f"{prefix}{lines}\n"


def _reveal_chunks(text: str, size: int = 24) -> list[str]:
    """Split an answer into fixed-size pieces for progressive reveal.

    Concatenating the pieces reproduces ``text`` exactly.
    """
    if not text:
        return []
    return [text[i : i + size] for i in range(0, len(text), size)]


@router.post("/stream")
async def query_stream(
    body: QueryRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """SSE variant of ``POST /query``.

    The graph runs to completion first — including faithfulness grading — and the
    finished answer is then revealed progressively. This is deliberate: streaming
    raw LLM tokens would put ungraded text in front of the user, and an answer
    that grading later flags ``faithful=false`` must never have already been
    rendered as trusted (Golden Rules 4 & 6). The final ``done`` frame carries the
    authoritative QueryResponse.
    """
    response = await _run_query(db, user, request, body.query, body.top_k)

    async def _events() -> AsyncIterator[str]:
        for piece in _reveal_chunks(response.answer):
            yield _sse_frame(piece)
        yield _sse_frame(response.model_dump_json(), event="done")

    return StreamingResponse(
        _events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
