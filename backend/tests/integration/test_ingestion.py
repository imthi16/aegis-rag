"""Ingestion integration (CLAUDE.md §10 — Ingestion DoD).

A txt upload yields chunks with valid offsets + persisted faiss_ids, FAISS
updated, document.ingested audit emitted, dedupe on repeat, and FAISS rollback
on failure. Uses a fake 1024-d embedder + temp FAISS/BM25 paths (no weights).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import app.ingestion.pipeline as pipeline
import numpy as np
import pytest
from app.core.config import get_settings
from app.db.models import AuditLog, Chunk, Document, Role, User
from app.ingestion.pipeline import ingest_document
from app.rbac.classifications import Classification
from app.rbac.classifications import Role as RoleEnum
from app.retrieval.bm25_index import get_bm25_index
from app.retrieval.faiss_store import get_faiss_store
from numpy.typing import NDArray
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


class _FakeEmbedder:
    def encode(self, texts: list[str], batch_size: int) -> NDArray[np.float32]:
        rng = np.random.default_rng(1234)
        vecs = rng.standard_normal((len(texts), 1024)).astype(np.float32)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        return (vecs / norms).astype(np.float32)


@pytest.fixture
def ingest_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("FAISS_INDEX_PATH", str(tmp_path / "faiss" / "index.faiss"))
    monkeypatch.setenv("BM25_INDEX_PATH", str(tmp_path / "bm25" / "bm25.pkl"))
    get_settings.cache_clear()
    get_faiss_store.cache_clear()
    get_bm25_index.cache_clear()
    monkeypatch.setattr(pipeline, "get_embedder", lambda: _FakeEmbedder())
    yield
    get_faiss_store.cache_clear()
    get_bm25_index.cache_clear()


async def _admin(db: AsyncSession) -> User:
    role = Role(name="admin", description="admin")
    db.add(role)
    await db.flush()
    user = User(username="up", hashed_password="x", roles=[role])
    db.add(user)
    await db.commit()
    return user


def _write_txt(tmp_path: Path, body: str) -> str:
    p = tmp_path / "doc.txt"
    p.write_text(body, encoding="utf-8")
    return str(p)


@pytest.mark.asyncio
async def test_ingest_persists_chunks_faiss_and_audit(
    ingest_env: None, db_session: AsyncSession, tmp_path: Path
) -> None:
    admin = await _admin(db_session)
    body = ("Sovereign RAG keeps data on-premise. " * 8) + "\n\n" + ("Audit is hash chained. " * 8)
    path = _write_txt(tmp_path, body)

    store = get_faiss_store()
    before = store.ntotal

    doc = await ingest_document(
        db_session,
        file_path=path,
        filename="doc.txt",
        filetype="txt",
        classification=Classification.INTERNAL,
        allowed_roles=[RoleEnum.ANALYST],
        uploaded_by=admin.id,
    )

    assert doc.status == "ready"
    assert doc.chunk_count > 0

    chunks = (
        (await db_session.execute(select(Chunk).where(Chunk.document_id == doc.id))).scalars().all()
    )
    assert len(chunks) == doc.chunk_count
    for c in chunks:
        assert c.char_start < c.char_end
        assert c.faiss_id > 0
        assert c.embedding_model == "bge-m3"

    assert store.ntotal == before + doc.chunk_count

    audits = (
        (await db_session.execute(select(AuditLog).where(AuditLog.action == "document.ingested")))
        .scalars()
        .all()
    )
    assert len(audits) == 1
    assert audits[0].resource_id == str(doc.id)


@pytest.mark.asyncio
async def test_ingest_dedupes_same_hash_and_classification(
    ingest_env: None, db_session: AsyncSession, tmp_path: Path
) -> None:
    admin = await _admin(db_session)
    path = _write_txt(tmp_path, "Identical content for dedupe. " * 10)

    first = await ingest_document(
        db_session,
        file_path=path,
        filename="a.txt",
        filetype="txt",
        classification=Classification.INTERNAL,
        allowed_roles=[RoleEnum.ANALYST],
        uploaded_by=admin.id,
    )
    second = await ingest_document(
        db_session,
        file_path=path,
        filename="b.txt",
        filetype="txt",
        classification=Classification.INTERNAL,
        allowed_roles=[RoleEnum.VIEWER],
        uploaded_by=admin.id,
    )
    assert first.id == second.id
    total_docs = await db_session.scalar(select(func.count()).select_from(Document))
    assert total_docs == 1


@pytest.mark.asyncio
async def test_reindex_reembeds_and_swaps_vectors(
    ingest_env: None, db_session: AsyncSession, tmp_path: Path
) -> None:
    """Reindex is a true rebuild of BOTH channels, not just a BM25 refresh."""
    admin = await _admin(db_session)
    path = _write_txt(tmp_path, "Original body about sovereign retrieval. " * 10)

    doc = await ingest_document(
        db_session,
        file_path=path,
        filename="doc.txt",
        filetype="txt",
        classification=Classification.INTERNAL,
        allowed_roles=[RoleEnum.ANALYST],
        uploaded_by=admin.id,
    )
    original_faiss_ids = {
        int(fid)
        for fid in (
            await db_session.execute(select(Chunk.faiss_id).where(Chunk.document_id == doc.id))
        )
        .scalars()
        .all()
    }
    store = get_faiss_store()
    ntotal_before = store.ntotal

    # Rewrite the stored original with longer content, then reindex.
    Path(path).write_text("Rewritten and expanded body. " * 40, encoding="utf-8")
    new_count = await pipeline.reindex_document(db_session, doc)
    await db_session.commit()

    assert new_count > 0
    assert doc.chunk_count == new_count

    new_faiss_ids = {
        int(fid)
        for fid in (
            await db_session.execute(select(Chunk.faiss_id).where(Chunk.document_id == doc.id))
        )
        .scalars()
        .all()
    }
    # Fresh vectors, and the stale ones retired rather than left orphaned.
    assert new_faiss_ids.isdisjoint(original_faiss_ids)
    assert len(new_faiss_ids) == new_count
    assert store.ntotal == ntotal_before - len(original_faiss_ids) + new_count

    # Content was genuinely re-parsed.
    contents = (
        (await db_session.execute(select(Chunk.content).where(Chunk.document_id == doc.id)))
        .scalars()
        .all()
    )
    assert any("Rewritten" in c for c in contents)


@pytest.mark.asyncio
async def test_reindex_without_stored_original_raises(
    ingest_env: None, db_session: AsyncSession, tmp_path: Path
) -> None:
    """A document whose original is gone fails loudly instead of half-reindexing."""
    admin = await _admin(db_session)
    path = _write_txt(tmp_path, "Body that will be removed from disk. " * 10)
    doc = await ingest_document(
        db_session,
        file_path=path,
        filename="doc.txt",
        filetype="txt",
        classification=Classification.INTERNAL,
        allowed_roles=[RoleEnum.ANALYST],
        uploaded_by=admin.id,
    )
    Path(path).unlink()

    with pytest.raises(FileNotFoundError):
        await pipeline.reindex_document(db_session, doc)


@pytest.mark.asyncio
async def test_ingest_rolls_back_faiss_on_failure(
    ingest_env: None, db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = await _admin(db_session)
    path = _write_txt(tmp_path, "Content that will fail to persist. " * 10)

    async def _boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("forced audit failure")

    monkeypatch.setattr(pipeline, "write_audit", _boom)

    store = get_faiss_store()
    before = store.ntotal

    with pytest.raises(RuntimeError):
        await ingest_document(
            db_session,
            file_path=path,
            filename="x.txt",
            filetype="txt",
            classification=Classification.CONFIDENTIAL,
            allowed_roles=[RoleEnum.ANALYST],
            uploaded_by=admin.id,
        )

    # FAISS additions were compensated; no document persisted.
    assert store.ntotal == before
    await db_session.rollback()
    docs = await db_session.scalar(select(func.count()).select_from(Document))
    assert docs == 0
