"""Hybrid retrieval RBAC isolation (CLAUDE.md §10 — Hybrid DoD, Golden Rule 3).

A viewer querying a corpus that contains a restricted doc never receives that
doc in candidates. Admin sees both. Uses a fake embedder + temp indexes.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import app.ingestion.pipeline as pipeline
import app.retrieval.hybrid as hybrid
import numpy as np
import pytest
from app.core.config import get_settings
from app.db.models import Role, User
from app.ingestion.pipeline import ingest_document
from app.rbac.classifications import Classification
from app.rbac.classifications import Role as RoleEnum
from app.retrieval.bm25_index import get_bm25_index
from app.retrieval.faiss_store import get_faiss_store
from app.retrieval.hybrid import hybrid_retrieve
from numpy.typing import NDArray
from sqlalchemy.ext.asyncio import AsyncSession


class _FakeEmbedder:
    def encode(self, texts: list[str], batch_size: int) -> NDArray[np.float32]:
        rng = np.random.default_rng(7)
        vecs = rng.standard_normal((len(texts), 1024)).astype(np.float32)
        return (vecs / np.linalg.norm(vecs, axis=1, keepdims=True)).astype(np.float32)

    def encode_query(self, text: str) -> NDArray[np.float32]:
        return self.encode([text], 1)[0]


@pytest.fixture
def retrieval_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("FAISS_INDEX_PATH", str(tmp_path / "faiss" / "index.faiss"))
    monkeypatch.setenv("BM25_INDEX_PATH", str(tmp_path / "bm25" / "bm25.pkl"))
    get_settings.cache_clear()
    get_faiss_store.cache_clear()
    get_bm25_index.cache_clear()
    fake = _FakeEmbedder()
    monkeypatch.setattr(pipeline, "get_embedder", lambda: fake)
    monkeypatch.setattr(hybrid, "get_embedder", lambda: fake)
    yield
    get_faiss_store.cache_clear()
    get_bm25_index.cache_clear()


async def _seed_users(db: AsyncSession) -> tuple[User, User]:
    roles = {name: Role(name=name, description=name) for name in ("admin", "viewer")}
    db.add_all(list(roles.values()))
    await db.flush()
    admin = User(username="adm", hashed_password="x", roles=[roles["admin"]])
    viewer = User(username="vw", hashed_password="x", roles=[roles["viewer"]])
    db.add_all([admin, viewer])
    await db.commit()
    return admin, viewer


@pytest.mark.asyncio
async def test_viewer_never_sees_restricted_doc(
    retrieval_env: None, db_session: AsyncSession, tmp_path: Path
) -> None:
    admin, viewer = await _seed_users(db_session)

    restricted_path = tmp_path / "restricted.txt"
    restricted_path.write_text("secret merger terms and financial projections " * 10)
    internal_path = tmp_path / "internal.txt"
    internal_path.write_text("public quarterly financial summary and projections " * 10)

    restricted = await ingest_document(
        db_session,
        file_path=str(restricted_path),
        filename="restricted.txt",
        filetype="txt",
        classification=Classification.RESTRICTED,
        allowed_roles=[RoleEnum.ADMIN],  # viewer excluded
        uploaded_by=admin.id,
    )
    internal = await ingest_document(
        db_session,
        file_path=str(internal_path),
        filename="internal.txt",
        filetype="txt",
        classification=Classification.INTERNAL,
        allowed_roles=[RoleEnum.VIEWER],
        uploaded_by=admin.id,
    )

    # Viewer: only the internal doc may ever surface.
    viewer_cands = await hybrid_retrieve(
        db_session, query="financial projections", user=viewer, top_k=20
    )
    assert viewer_cands, "viewer should see the internal doc"
    seen_docs = {c.document_id for c in viewer_cands}
    assert restricted.id not in seen_docs
    assert seen_docs == {internal.id}

    # Admin: sees both documents.
    admin_cands = await hybrid_retrieve(
        db_session, query="financial projections", user=admin, top_k=20
    )
    admin_docs = {c.document_id for c in admin_cands}
    assert restricted.id in admin_docs
    assert internal.id in admin_docs


@pytest.mark.asyncio
async def test_user_with_no_roles_gets_nothing(
    retrieval_env: None, db_session: AsyncSession, tmp_path: Path
) -> None:
    admin, _ = await _seed_users(db_session)
    path = tmp_path / "doc.txt"
    path.write_text("some internal content here " * 10)
    await ingest_document(
        db_session,
        file_path=str(path),
        filename="doc.txt",
        filetype="txt",
        classification=Classification.INTERNAL,
        allowed_roles=[RoleEnum.ANALYST],
        uploaded_by=admin.id,
    )
    roleless = User(username="noroles", hashed_password="x", roles=[])
    db_session.add(roleless)
    await db_session.commit()

    cands = await hybrid_retrieve(db_session, query="internal content", user=roleless, top_k=10)
    assert cands == []
