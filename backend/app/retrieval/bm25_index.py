"""BM25 lexical index (CLAUDE.md §6.7).

Persisted BM25Okapi over the tokenized chunk corpus, keyed by faiss_id. Tokenizer
is simple/deterministic/offline (lowercase + unicode word split). rank_bm25 is
immutable, so ``add`` rebuilds the model over the accumulated corpus. Honors the
same ``allowed_faiss_ids`` RBAC filter as the dense index.
"""

from __future__ import annotations

import pickle  # noqa: S403  (trusted, locally-written index file only)
import re
import threading
from functools import lru_cache

from rank_bm25 import BM25Okapi

from app.core.config import get_settings

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class BM25Index:
    def __init__(self) -> None:
        self._ids: list[int] = []
        self._tokens: list[list[str]] = []
        self._bm25: BM25Okapi | None = None
        self._lock = threading.Lock()

    def _rebuild(self) -> None:
        self._bm25 = BM25Okapi(self._tokens) if self._tokens else None

    def build(self, corpus: list[tuple[int, str]]) -> None:
        with self._lock:
            self._ids = [fid for fid, _ in corpus]
            self._tokens = [tokenize(text) for _, text in corpus]
            self._rebuild()

    def add(self, items: list[tuple[int, str]]) -> None:
        if not items:
            return
        with self._lock:
            for fid, text in items:
                self._ids.append(fid)
                self._tokens.append(tokenize(text))
            self._rebuild()

    def search(
        self,
        query: str,
        top_k: int,
        allowed_faiss_ids: set[int] | None = None,
    ) -> list[tuple[int, float]]:
        if self._bm25 is None or top_k <= 0:
            return []
        if allowed_faiss_ids is not None and not allowed_faiss_ids:
            return []

        scores = self._bm25.get_scores(tokenize(query))
        pairs: list[tuple[int, float]] = []
        for fid, score in zip(self._ids, scores.tolist(), strict=True):
            if allowed_faiss_ids is not None and fid not in allowed_faiss_ids:
                continue
            pairs.append((int(fid), float(score)))
        pairs.sort(key=lambda x: x[1], reverse=True)
        return pairs[:top_k]

    def save(self) -> None:
        import os

        path = get_settings().bm25_index_path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with self._lock, open(path, "wb") as fh:
            pickle.dump({"ids": self._ids, "tokens": self._tokens}, fh)

    def load(self) -> None:
        path = get_settings().bm25_index_path
        with open(path, "rb") as fh:
            data = pickle.load(fh)  # noqa: S301  (trusted local file)
        with self._lock:
            self._ids = list(data["ids"])
            self._tokens = list(data["tokens"])
            self._rebuild()

    @property
    def size(self) -> int:
        return len(self._ids)


@lru_cache
def get_bm25_index() -> BM25Index:
    import os

    index = BM25Index()
    if os.path.exists(get_settings().bm25_index_path):
        index.load()
    return index
