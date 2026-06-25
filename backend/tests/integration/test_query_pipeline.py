"""Query pipeline integration (CLAUDE.md §10 — Graph DoD).

End-to-end via HTTP with fake embedder/reranker/LLM: a faithful cited answer,
the insufficient-evidence path, and a low-faithfulness regen landing on
faithful=false. Each query writes one query_log + one query.executed audit row.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import app.ingestion.pipeline as pipeline
import app.retrieval.hybrid as hybrid
import numpy as np
import pytest
from app.core.config import get_settings
from app.core.security import hash_password
from app.db.models import AuditLog, QueryLog, Role, User
from app.ingestion.pipeline import ingest_document
from app.rbac.classifications import Classification
from app.rbac.classifications import Role as RoleEnum
from app.retrieval.bm25_index import get_bm25_index
from app.retrieval.faiss_store import get_faiss_store
from httpx import AsyncClient
from numpy.typing import NDArray
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


class _FakeEmbedder:
    def encode(self, texts: list[str], batch_size: int) -> NDArray[np.float32]:
        rng = np.random.default_rng(3)
        vecs = rng.standard_normal((len(texts), 1024)).astype(np.float32)
        return (vecs / np.linalg.norm(vecs, axis=1, keepdims=True)).astype(np.float32)

    def encode_query(self, text: str) -> NDArray[np.float32]:
        return self.encode([text], 1)[0]


class _FakeReranker:
    def rerank(self, query: str, candidates: list, top_n: int) -> list:  # type: ignore[type-arg]
        return candidates[:top_n]


class _FakeLLM:
    def __init__(self, relevant: bool = True, rel_score: float = 0.9, faith: float = 0.95) -> None:
        self.relevant = relevant
        self.rel_score = rel_score
        self.faith = faith

    async def chat(
        self, messages: list[dict[str, str]], *, temperature: float, num_ctx: int, format: str = ""
    ) -> str:
        sys = messages[0]["content"].lower()
        if format == "json" and "relevant" in sys:
            return json.dumps({"relevant": self.relevant, "score": self.rel_score})
        if format == "json" and "faithful" in sys:
            return json.dumps({"faithful": self.faith >= 0.7, "score": self.faith})
        if "rewrite" in sys:
            return "rewritten financial projections query"
        return "The quarterly figures are summarized here [1]."


def _patch(monkeypatch: pytest.MonkeyPatch, llm: _FakeLLM) -> None:
    emb = _FakeEmbedder()
    monkeypatch.setattr(pipeline, "get_embedder", lambda: emb)
    monkeypatch.setattr(hybrid, "get_embedder", lambda: emb)
    monkeypatch.setattr("app.graph.nodes.rerank.get_reranker", lambda: _FakeReranker())
    for mod in ("grade_documents", "transform_query", "generate", "grade_faithfulness"):
        monkeypatch.setattr(f"app.graph.nodes.{mod}.get_llm", lambda: llm)


@pytest.fixture
def pipeline_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("FAISS_INDEX_PATH", str(tmp_path / "faiss" / "i.faiss"))
    monkeypatch.setenv("BM25_INDEX_PATH", str(tmp_path / "bm25" / "b.pkl"))
    # Small chunks so a single fixture doc yields >= CRAG_MIN_RELEVANT_DOCS chunks.
    monkeypatch.setenv("CHUNK_SIZE_TOKENS", "20")
    monkeypatch.setenv("CHUNK_OVERLAP_TOKENS", "5")
    get_settings.cache_clear()
    get_faiss_store.cache_clear()
    get_bm25_index.cache_clear()
    yield
    get_faiss_store.cache_clear()
    get_bm25_index.cache_clear()


async def _viewer(db: AsyncSession, password: str) -> User:
    role = Role(name="viewer", description="viewer")
    db.add(role)
    await db.flush()
    user = User(username="vw", hashed_password=hash_password(password), roles=[role])
    db.add(user)
    await db.commit()
    return user


async def _ingest_viewer_doc(db: AsyncSession, tmp_path: Path, uploader: User) -> None:
    p = tmp_path / "doc.txt"
    p.write_text("Quarterly financial projections and figures. " * 12)
    await ingest_document(
        db,
        file_path=str(p),
        filename="doc.txt",
        filetype="txt",
        classification=Classification.INTERNAL,
        allowed_roles=[RoleEnum.VIEWER],
        uploaded_by=uploader.id,
    )


async def _login(client: AsyncClient, password: str) -> str:
    resp = await client.post("/api/v1/auth/login", json={"username": "vw", "password": password})
    assert resp.status_code == 200
    return str(resp.json()["access_token"])


@pytest.mark.asyncio
async def test_faithful_cited_answer(
    pipeline_env: None,
    client: AsyncClient,
    db_session: AsyncSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pw = "pw-12345678"
    _patch(monkeypatch, _FakeLLM(relevant=True, rel_score=0.9, faith=0.95))
    user = await _viewer(db_session, pw)
    await _ingest_viewer_doc(db_session, tmp_path, user)

    token = await _login(client, pw)
    resp = await client.post(
        "/api/v1/query",
        json={"query": "what are the projections?"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["insufficient_evidence"] is False
    assert body["faithful"] is True
    assert body["citations"], "expected at least one citation"
    assert body["retrieved_chunks"]
    assert body["correction_applied"] is False

    assert (await db_session.scalar(select(func.count()).select_from(QueryLog))) == 1
    executed = (
        (await db_session.execute(select(AuditLog).where(AuditLog.action == "query.executed")))
        .scalars()
        .all()
    )
    assert len(executed) == 1


@pytest.mark.asyncio
async def test_insufficient_evidence_when_no_accessible_docs(
    pipeline_env: None,
    client: AsyncClient,
    db_session: AsyncSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pw = "pw-12345678"
    _patch(monkeypatch, _FakeLLM())
    await _viewer(db_session, pw)
    analyst = Role(name="analyst", description="analyst")
    db_session.add(analyst)
    await db_session.flush()
    uploader = User(username="an", hashed_password="x", roles=[analyst])
    db_session.add(uploader)
    await db_session.commit()

    p = tmp_path / "secret.txt"
    p.write_text("Confidential analyst-only content. " * 12)
    await ingest_document(
        db_session,
        file_path=str(p),
        filename="secret.txt",
        filetype="txt",
        classification=Classification.CONFIDENTIAL,
        allowed_roles=[RoleEnum.ANALYST],
        uploaded_by=uploader.id,
    )

    token = await _login(client, pw)
    resp = await client.post(
        "/api/v1/query",
        json={"query": "what is the secret?"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["insufficient_evidence"] is True
    assert body["faithful"] is False
    assert body["citations"] == []


@pytest.mark.asyncio
async def test_low_faithfulness_finalizes_unfaithful(
    pipeline_env: None,
    client: AsyncClient,
    db_session: AsyncSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pw = "pw-12345678"
    _patch(monkeypatch, _FakeLLM(relevant=True, rel_score=0.9, faith=0.1))
    user = await _viewer(db_session, pw)
    await _ingest_viewer_doc(db_session, tmp_path, user)

    token = await _login(client, pw)
    resp = await client.post(
        "/api/v1/query",
        json={"query": "what are the projections?"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["faithful"] is False
    assert body["correction_applied"] is False
