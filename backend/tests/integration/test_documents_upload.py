"""Upload route integration (CLAUDE.md §6.18, §7 Documents).

An uploader may only grant roles within its own authority — enforced by the API,
not just the UI, so the endpoint cannot be used to widen a document's audience
beyond the uploader's own access. Also covers the retained-original contract that
makes /documents/{id}/reindex possible.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import app.ingestion.pipeline as pipeline
import numpy as np
import pytest
from app.core.config import get_settings
from app.core.security import hash_password
from app.db.models import Document, Role, User
from app.retrieval.bm25_index import get_bm25_index
from app.retrieval.faiss_store import get_faiss_store
from httpx import AsyncClient
from numpy.typing import NDArray
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_PASSWORD = "upload-pw-12345"


class _FakeEmbedder:
    def encode(self, texts: list[str], batch_size: int) -> NDArray[np.float32]:
        rng = np.random.default_rng(7)
        vecs = rng.standard_normal((len(texts), 1024)).astype(np.float32)
        return (vecs / np.linalg.norm(vecs, axis=1, keepdims=True)).astype(np.float32)


@pytest.fixture
def upload_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    storage = tmp_path / "documents"
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("FAISS_INDEX_PATH", str(tmp_path / "faiss" / "i.faiss"))
    monkeypatch.setenv("BM25_INDEX_PATH", str(tmp_path / "bm25" / "b.pkl"))
    monkeypatch.setenv("DOCUMENT_STORAGE_PATH", str(storage))
    get_settings.cache_clear()
    get_faiss_store.cache_clear()
    get_bm25_index.cache_clear()
    monkeypatch.setattr(pipeline, "get_embedder", lambda: _FakeEmbedder())
    yield storage
    get_faiss_store.cache_clear()
    get_bm25_index.cache_clear()


async def _user_with_roles(db: AsyncSession, username: str, *role_names: str) -> User:
    roles = []
    for name in role_names:
        existing = await db.scalar(select(Role).where(Role.name == name))
        if existing is None:
            existing = Role(name=name, description=name)
            db.add(existing)
            await db.flush()
        roles.append(existing)
    user = User(username=username, hashed_password=hash_password(_PASSWORD), roles=list(roles))
    db.add(user)
    await db.commit()
    return user


async def _token(client: AsyncClient, username: str) -> str:
    resp = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": _PASSWORD}
    )
    assert resp.status_code == 200, resp.text
    return str(resp.json()["access_token"])


def _file() -> dict[str, tuple[str, bytes, str]]:
    body = ("Retention policy details for the archive. " * 12).encode()
    return {"file": ("policy.txt", body, "text/plain")}


@pytest.mark.asyncio
async def test_analyst_cannot_grant_roles_it_does_not_hold(
    upload_env: Path, client: AsyncClient, db_session: AsyncSession
) -> None:
    await _user_with_roles(db_session, "an", "analyst")
    token = await _token(client, "an")

    resp = await client.post(
        "/api/v1/documents",
        files=_file(),
        data={"classification": "internal", "allowed_roles": ["viewer"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"
    # Nothing was persisted.
    assert (await db_session.scalar(select(Document))) is None


@pytest.mark.asyncio
async def test_analyst_cannot_grant_admin(
    upload_env: Path, client: AsyncClient, db_session: AsyncSession
) -> None:
    await _user_with_roles(db_session, "an", "analyst")
    token = await _token(client, "an")

    resp = await client.post(
        "/api/v1/documents",
        files=_file(),
        data={"classification": "restricted", "allowed_roles": ["analyst", "admin"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_analyst_may_grant_its_own_role(
    upload_env: Path, client: AsyncClient, db_session: AsyncSession
) -> None:
    await _user_with_roles(db_session, "an", "analyst")
    token = await _token(client, "an")

    resp = await client.post(
        "/api/v1/documents",
        files=_file(),
        data={"classification": "internal", "allowed_roles": ["analyst"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["allowed_roles"] == ["analyst"]


@pytest.mark.asyncio
async def test_admin_may_grant_any_role(
    upload_env: Path, client: AsyncClient, db_session: AsyncSession
) -> None:
    await _user_with_roles(db_session, "ad", "admin")
    token = await _token(client, "ad")

    resp = await client.post(
        "/api/v1/documents",
        files=_file(),
        data={
            "classification": "confidential",
            "allowed_roles": ["viewer", "analyst", "compliance_auditor"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert set(resp.json()["allowed_roles"]) == {"viewer", "analyst", "compliance_auditor"}


@pytest.mark.asyncio
async def test_upload_retains_the_original_for_reindex(
    upload_env: Path, client: AsyncClient, db_session: AsyncSession
) -> None:
    """source_path must point at a file that still exists (§8: stored original)."""
    await _user_with_roles(db_session, "ad", "admin")
    token = await _token(client, "ad")

    resp = await client.post(
        "/api/v1/documents",
        files=_file(),
        data={"classification": "internal", "allowed_roles": ["analyst"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    doc_id = resp.json()["id"]

    doc = await db_session.get(Document, doc_id)
    assert doc is not None
    assert doc.source_path
    assert os.path.exists(doc.source_path), "stored original is missing; reindex would fail"
    assert str(upload_env) in doc.source_path

    # And the route can therefore actually reindex it.
    reindex = await client.post(
        f"/api/v1/documents/{doc_id}/reindex",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert reindex.status_code == 202


@pytest.mark.asyncio
async def test_delete_removes_the_retained_original(
    upload_env: Path, client: AsyncClient, db_session: AsyncSession
) -> None:
    await _user_with_roles(db_session, "ad", "admin")
    token = await _token(client, "ad")

    resp = await client.post(
        "/api/v1/documents",
        files=_file(),
        data={"classification": "internal", "allowed_roles": ["analyst"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    doc_id = resp.json()["id"]
    doc = await db_session.get(Document, doc_id)
    assert doc is not None
    stored = doc.source_path
    assert stored and os.path.exists(stored)

    delete = await client.delete(
        f"/api/v1/documents/{doc_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert delete.status_code == 200
    assert not os.path.exists(stored), "deleting a document must not leave its content on disk"
