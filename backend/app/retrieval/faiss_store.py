"""FAISS dense index (CLAUDE.md §6.6).

IndexIDMap2 over IndexFlatIP (cosine via normalized vectors) or IndexHNSWFlat.
faiss_id is a stable 63-bit int generated at chunk insert and stored in Postgres.

RBAC pre-filter: when ``allowed_faiss_ids`` is provided we over-fetch
``top_k * OVERFETCH_FACTOR``, drop ids outside the allowed set, and truncate to
``top_k``. This robust path works for every index type (robustness > cleverness,
per the spec).
"""

from __future__ import annotations

import os
import threading
from functools import lru_cache

import faiss
import numpy as np
from numpy.typing import NDArray

from app.core.config import get_settings
from app.core.logging import get_logger

FloatArray = NDArray[np.float32]

logger = get_logger("app.faiss")


class FaissStore:
    def __init__(self, index_path: str, dim: int, index_type: str) -> None:
        self.index_path = index_path
        self.dim = dim
        self.index_type = index_type
        self._index: faiss.Index | None = None
        self._lock = threading.Lock()

    # ── lifecycle ───────────────────────────────────────────
    def _new_index(self) -> faiss.Index:
        settings = get_settings()
        if self.index_type == "hnsw":
            base = faiss.IndexHNSWFlat(self.dim, settings.faiss_hnsw_m, faiss.METRIC_INNER_PRODUCT)
            base.hnsw.efSearch = settings.faiss_hnsw_ef_search
        else:
            base = faiss.IndexFlatIP(self.dim)
        return faiss.IndexIDMap2(base)

    def load_or_create(self) -> None:
        if os.path.exists(self.index_path):
            self._index = faiss.read_index(self.index_path)
        else:
            self._index = self._new_index()
            self.save()

    def _require(self) -> faiss.Index:
        if self._index is None:
            self.load_or_create()
        if self._index is None:
            raise RuntimeError("FAISS index not initialized")
        return self._index

    # ── mutations ───────────────────────────────────────────
    def add(self, vectors: FloatArray, ids: list[int]) -> None:
        index = self._require()
        vecs = np.ascontiguousarray(vectors, dtype=np.float32)
        id_arr = np.asarray(ids, dtype=np.int64)
        with self._lock:
            index.add_with_ids(vecs, id_arr)

    def remove(self, ids: list[int]) -> None:
        index = self._require()
        id_arr = np.asarray(ids, dtype=np.int64)
        with self._lock:
            index.remove_ids(id_arr)

    # ── search ──────────────────────────────────────────────
    def search(
        self,
        query: FloatArray,
        top_k: int,
        allowed_faiss_ids: set[int] | None = None,
    ) -> list[tuple[int, float]]:
        index = self._require()
        if index.ntotal == 0 or top_k <= 0:
            return []

        q = np.ascontiguousarray(query, dtype=np.float32)
        if q.ndim == 1:
            q = q.reshape(1, -1)

        if allowed_faiss_ids is None:
            fetch = top_k
        else:
            if not allowed_faiss_ids:
                return []
            factor = max(1, get_settings().overfetch_factor)
            fetch = min(top_k * factor, index.ntotal)

        scores, ids = index.search(q, fetch)
        results: list[tuple[int, float]] = []
        for fid, score in zip(ids[0].tolist(), scores[0].tolist(), strict=True):
            if fid == -1:
                continue
            if allowed_faiss_ids is not None and fid not in allowed_faiss_ids:
                continue
            results.append((int(fid), float(score)))
            if len(results) >= top_k:
                break
        return results

    def save(self) -> None:
        if self._index is None:
            return
        os.makedirs(os.path.dirname(self.index_path) or ".", exist_ok=True)
        with self._lock:
            faiss.write_index(self._index, self.index_path)

    @property
    def ntotal(self) -> int:
        return int(self._require().ntotal)


@lru_cache
def get_faiss_store() -> FaissStore:
    settings = get_settings()
    store = FaissStore(
        index_path=settings.faiss_index_path,
        dim=settings.embedding_dim,
        index_type=settings.faiss_index_type,
    )
    store.load_or_create()
    return store


def is_ready() -> bool:
    """True once the store singleton is loaded (does not trigger a load)."""
    return get_faiss_store.cache_info().currsize > 0
