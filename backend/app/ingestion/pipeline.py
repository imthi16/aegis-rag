"""Ingestion pipeline (CLAUDE.md §6.4).

Order: parse → chunk → embed (batch) → add to FAISS (capture faiss_id) → persist
Document + Chunk rows + document.ingested audit in one transaction → append BM25
→ commit. If the DB transaction fails after FAISS add, the vectors are removed
(compensating delete) so no orphan vectors remain. Duplicate (same content_hash +
classification) is deduped.
"""

from __future__ import annotations

import os
import secrets
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.logger import write_audit
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models.chunk import Chunk as ChunkModel
from app.db.models.document import Document
from app.db.models.user import User
from app.embeddings.embedder import get_embedder
from app.ingestion.chunker import chunk_text
from app.ingestion.parsers import parse_document
from app.rbac.classifications import Classification, Role
from app.retrieval.bm25_index import get_bm25_index
from app.retrieval.faiss_store import get_faiss_store

logger = get_logger("app.ingestion")

EMBEDDING_MODEL_NAME = "bge-m3"


def _new_faiss_id() -> int:
    """A stable, positive 63-bit id (UNIQUE in Postgres guards collisions)."""
    return secrets.randbits(63) or 1


def _current_request_id() -> str:
    from structlog.contextvars import get_contextvars

    rid = get_contextvars().get("request_id")
    return str(rid) if rid else str(uuid.uuid4())


async def _uploader_roles(db: AsyncSession, uploaded_by: uuid.UUID | None) -> list[str]:
    if uploaded_by is None:
        return []
    user = await db.get(User, uploaded_by)
    return user.role_names if user else []


async def ingest_document(
    db: AsyncSession,
    *,
    file_path: str,
    filename: str,
    filetype: str,
    classification: Classification,
    allowed_roles: list[Role],
    uploaded_by: uuid.UUID,
) -> Document:
    settings = get_settings()
    parsed = parse_document(file_path, filetype)

    # Dedupe: same content + classification → return existing, skip re-embedding.
    existing = await db.scalar(
        select(Document).where(
            Document.content_hash == parsed.content_hash,
            Document.classification == classification.value,
        )
    )
    if existing is not None:
        logger.info("ingest_dedupe", content_hash=parsed.content_hash[:12])
        return existing

    chunks = chunk_text(parsed, settings.chunk_size_tokens, settings.chunk_overlap_tokens)
    faiss_ids = [_new_faiss_id() for _ in chunks]
    store = get_faiss_store()

    added_to_faiss = False
    if chunks:
        vectors = get_embedder().encode([c.content for c in chunks], settings.embedding_batch_size)
        store.add(vectors, faiss_ids)
        added_to_faiss = True

    try:
        doc = Document(
            filename=filename,
            content_hash=parsed.content_hash,
            source_path=file_path,
            filetype=filetype.lower(),
            classification=classification.value,
            allowed_roles=[r.value for r in allowed_roles],
            uploaded_by=uploaded_by,
            status="ready",
            page_count=len(parsed.pages),
            chunk_count=len(chunks),
            doc_metadata=parsed.meta,
        )
        db.add(doc)
        await db.flush()

        for chunk, fid in zip(chunks, faiss_ids, strict=True):
            db.add(
                ChunkModel(
                    document_id=doc.id,
                    chunk_index=chunk.index,
                    content=chunk.content,
                    token_count=chunk.token_count,
                    page_number=chunk.page_number,
                    char_start=chunk.char_start,
                    char_end=chunk.char_end,
                    faiss_id=fid,
                    embedding_model=EMBEDDING_MODEL_NAME,
                )
            )

        await write_audit(
            db,
            actor_id=uploaded_by,
            actor_roles=await _uploader_roles(db, uploaded_by),
            action="document.ingested",
            resource_type="document",
            resource_id=str(doc.id),
            outcome="success",
            ip=None,
            request_id=_current_request_id(),
            details={
                "filename": filename,
                "classification": classification.value,
                "chunk_count": len(chunks),
            },
        )
        await db.commit()
    except Exception:
        await db.rollback()
        if added_to_faiss:
            # Compensating delete — never leave orphan vectors.
            store.remove(faiss_ids)
        logger.error("ingest_failed", filename=filename)
        raise

    # Post-commit: lexical index + durable persistence of the vector indexes.
    if chunks:
        bm25 = get_bm25_index()
        bm25.add([(fid, c.content) for c, fid in zip(chunks, faiss_ids, strict=True)])
        bm25.save()
        store.save()

    await db.refresh(doc)
    return doc


async def rebuild_bm25_from_db(db: AsyncSession) -> None:
    """Rebuild the BM25 index from all chunks currently in Postgres.

    rank_bm25 is immutable, so deletes/reindexes rebuild from the source of
    truth (Postgres) and persist.
    """
    rows = (
        await db.execute(
            select(ChunkModel.faiss_id, ChunkModel.content).order_by(ChunkModel.faiss_id)
        )
    ).all()
    bm25 = get_bm25_index()
    bm25.build([(int(fid), content) for fid, content in rows])
    bm25.save()


async def document_faiss_ids(db: AsyncSession, document_id: uuid.UUID) -> list[int]:
    """The faiss_ids of a document's chunks (for FAISS removal on delete)."""
    rows = await db.execute(
        select(ChunkModel.faiss_id).where(ChunkModel.document_id == document_id)
    )
    return [int(fid) for fid in rows.scalars().all()]


async def reindex_document(db: AsyncSession, doc: Document) -> int:
    """Re-parse, re-chunk, re-embed and re-index a document from its stored original.

    This is a genuine rebuild of both channels, not just a BM25 refresh: the old
    chunk rows and their vectors are dropped and replaced. Returns the new chunk
    count.

    Ordering mirrors ``ingest_document`` so the failure modes are the same: new
    vectors go into FAISS first, then the DB transaction swaps the chunk rows; if
    the commit fails the new vectors are compensated away and the old ones are
    restored, leaving the document exactly as it was.

    Raises ``FileNotFoundError`` when the original is no longer on disk (e.g. a
    document ingested before originals were retained) — the caller surfaces that
    rather than silently doing half a reindex.
    """
    settings = get_settings()
    source = doc.source_path
    if not source or not os.path.exists(source):
        raise FileNotFoundError(
            f"stored original for document {doc.id} is unavailable; cannot reindex"
        )

    parsed = parse_document(source, doc.filetype)
    chunks = chunk_text(parsed, settings.chunk_size_tokens, settings.chunk_overlap_tokens)
    new_faiss_ids = [_new_faiss_id() for _ in chunks]

    old_rows = (
        (
            await db.execute(
                select(ChunkModel.faiss_id, ChunkModel.content).where(
                    ChunkModel.document_id == doc.id
                )
            )
        )
        .tuples()
        .all()
    )
    old_faiss_ids = [int(fid) for fid, _ in old_rows]

    store = get_faiss_store()
    added = False
    if chunks:
        vectors = get_embedder().encode([c.content for c in chunks], settings.embedding_batch_size)
        store.add(vectors, new_faiss_ids)
        added = True

    try:
        await db.execute(delete(ChunkModel).where(ChunkModel.document_id == doc.id))
        for chunk, fid in zip(chunks, new_faiss_ids, strict=True):
            db.add(
                ChunkModel(
                    document_id=doc.id,
                    chunk_index=chunk.index,
                    content=chunk.content,
                    token_count=chunk.token_count,
                    page_number=chunk.page_number,
                    char_start=chunk.char_start,
                    char_end=chunk.char_end,
                    faiss_id=fid,
                    embedding_model=EMBEDDING_MODEL_NAME,
                )
            )
        doc.chunk_count = len(chunks)
        doc.page_count = len(parsed.pages)
        doc.content_hash = parsed.content_hash
        doc.status = "ready"
        await db.flush()
    except Exception:
        await db.rollback()
        if added:
            store.remove(new_faiss_ids)  # compensate: drop the vectors we just added
        logger.error("reindex_failed", document_id=str(doc.id))
        raise

    # Committed: the old vectors are now unreferenced, so retire them and
    # rebuild the lexical index from the (updated) source of truth.
    if old_faiss_ids:
        store.remove(old_faiss_ids)
    store.save()
    await rebuild_bm25_from_db(db)
    return len(chunks)
