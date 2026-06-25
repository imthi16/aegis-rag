"""FAISS store unit tests (CLAUDE.md §10 — Embeddings/FAISS/BM25 DoD).

add/search round-trips ids; allowed_faiss_ids RBAC filter honored; remove works;
save/load persists across a fresh instance.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from app.retrieval.faiss_store import FaissStore

DIM = 4
V = {
    10: [1.0, 0.0, 0.0, 0.0],
    20: [0.0, 1.0, 0.0, 0.0],
    30: [0.0, 0.0, 1.0, 0.0],
}


def _store(tmp_path: Path) -> FaissStore:
    store = FaissStore(index_path=str(tmp_path / "index.faiss"), dim=DIM, index_type="flat_ip")
    store.load_or_create()
    return store


def _add_all(store: FaissStore) -> None:
    ids = list(V.keys())
    vecs = np.array([V[i] for i in ids], dtype=np.float32)
    store.add(vecs, ids)


def test_add_and_search_round_trips_ids(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _add_all(store)
    q = np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)  # closest to id 20
    results = store.search(q, top_k=2)
    assert results[0][0] == 20
    assert pytest.approx(results[0][1], abs=1e-5) == 1.0


def test_rbac_filter_excludes_disallowed(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _add_all(store)
    q = np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)
    results = store.search(q, top_k=3, allowed_faiss_ids={10, 30})
    ids = {fid for fid, _ in results}
    assert 20 not in ids
    assert ids <= {10, 30}


def test_empty_allowed_set_returns_nothing(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _add_all(store)
    q = np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)
    assert store.search(q, top_k=3, allowed_faiss_ids=set()) == []


def test_remove_drops_id(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _add_all(store)
    store.remove([20])
    q = np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)
    ids = {fid for fid, _ in store.search(q, top_k=3)}
    assert 20 not in ids


def test_save_and_load_persists(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _add_all(store)
    store.save()

    reopened = FaissStore(index_path=str(tmp_path / "index.faiss"), dim=DIM, index_type="flat_ip")
    reopened.load_or_create()
    assert reopened.ntotal == 3
    q = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    assert reopened.search(q, top_k=1)[0][0] == 10
