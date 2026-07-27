"""Hybrid retrieval entrypoint (CLAUDE.md §6.9).

Order (RBAC first, always):
  1. allowed_document_ids(user) → the authoritative gate.
  2. dense (FAISS) + lexical (BM25), each RBAC-filtered by allowed faiss_ids.
  3. fuse with RRF.
  4. hydrate fused ids → Candidate from Postgres, re-asserting RBAC (defense in
     depth: drop any chunk whose document is not visible).
  5. return top_k. Empty allowed set → [] (graph reports insufficient evidence).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.chunk import Chunk
from app.db.models.user import User
from app.embeddings.embedder import get_embedder
from app.rbac.enforcement import allowed_document_ids, filter_chunk_candidates, is_admin
from app.retrieval.bm25_index import get_bm25_index
from app.retrieval.faiss_store import get_faiss_store
from app.retrieval.rrf import reciprocal_rank_fusion


@dataclass
class Candidate:
    faiss_id: int
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    content: str
    char_start: int
    char_end: int
    page_number: int | None
    score: float


async def _allowed_faiss_ids(db: AsyncSession, allowed_doc_ids: set[uuid.UUID]) -> set[int]:
    if not allowed_doc_ids:
        return set()
    rows = await db.execute(select(Chunk.faiss_id).where(Chunk.document_id.in_(allowed_doc_ids)))
    return {int(fid) for fid in rows.scalars().all()}


async def hybrid_retrieve(
    db: AsyncSession, *, query: str, user: User, top_k: int
) -> list[Candidate]:
    settings = get_settings()

    # 1) RBAC gate — computed before any search.
    allowed_docs = await allowed_document_ids(db, user)
    if not allowed_docs:
        return []

    # Admin sees everything → no per-id filter needed; others get the id set.
    if is_admin(user):
        faiss_filter: set[int] | None = None
    else:
        faiss_filter = await _allowed_faiss_ids(db, allowed_docs)
        if not faiss_filter:
            return []

    # 2) Dense + lexical, both RBAC-filtered.
    query_vec = get_embedder().encode_query(query)
    dense = get_faiss_store().search(query_vec, top_k, allowed_faiss_ids=faiss_filter)
    lexical = get_bm25_index().search(query, top_k, allowed_faiss_ids=faiss_filter)

    # 3) Fuse on ranks only.
    fused = reciprocal_rank_fusion(
        [[fid for fid, _ in dense], [fid for fid, _ in lexical]],
        k=settings.rrf_k,
    )
    if not fused:
        return []
    rrf_scores = dict(fused)
    ordered_ids = [fid for fid, _ in fused][:top_k]

    # 4) Hydrate, preserving fusion order.
    rows = (await db.execute(select(Chunk).where(Chunk.faiss_id.in_(ordered_ids)))).scalars().all()
    by_fid = {c.faiss_id: c for c in rows}

    hydrated: list[Candidate] = []
    for fid in ordered_ids:
        chunk = by_fid.get(fid)
        if chunk is None:
            continue
        hydrated.append(
            Candidate(
                faiss_id=fid,
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                content=chunk.content,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
                page_number=chunk.page_number,
                score=rrf_scores[fid],
            )
        )

    # 5) Re-assert RBAC on the hydrated rows (defense in depth): even though the
    # candidate ids were filtered pre-ranking, drop anything whose document is not
    # visible. Routed through the shared gate (§6.3) rather than an inline check so
    # both enforcement points cannot drift apart.
    return filter_chunk_candidates(hydrated, allowed_docs)[:top_k]
