"""BGE-M3 embedder singleton (CLAUDE.md §6.5).

Loads ``BGEM3FlagModel`` once from a pre-staged, offline path and returns
float32, L2-normalized dense vectors (so FAISS inner product == cosine). The
heavy import (FlagEmbedding/torch) is lazy so this module can be imported
without the weights present (e.g. for the readiness probe).
"""

from __future__ import annotations

import os
from functools import lru_cache

import numpy as np
from numpy.typing import NDArray

from app.core.config import get_settings

FloatArray = NDArray[np.float32]


def _l2_normalize(vectors: FloatArray) -> FloatArray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.where(norms == 0.0, 1.0, norms)
    result: FloatArray = (vectors / norms).astype(np.float32)
    return result


class Embedder:
    """Wrapper over BGEM3FlagModel returning (n, dim) float32 vectors."""

    def __init__(self, model_path: str, device: str, max_length: int, normalize: bool) -> None:
        # Offline by env, defensively, before importing the model library.
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        from FlagEmbedding import BGEM3FlagModel  # lazy heavy import

        self.dim = get_settings().embedding_dim
        self.max_length = max_length
        self.normalize = normalize
        self._model = BGEM3FlagModel(model_path, use_fp16=(device != "cpu"), devices=device)

    def encode(self, texts: list[str], batch_size: int) -> FloatArray:
        if not texts:
            empty: FloatArray = np.zeros((0, self.dim), dtype=np.float32)
            return empty
        output = self._model.encode(texts, batch_size=batch_size, max_length=self.max_length)
        dense: FloatArray = np.asarray(output["dense_vecs"], dtype=np.float32)
        if dense.ndim == 1:
            dense = dense.reshape(1, -1)
        if self.normalize:
            dense = _l2_normalize(dense)
        return dense

    def encode_query(self, text: str) -> FloatArray:
        vec: FloatArray = self.encode([text], batch_size=1)[0]
        return vec


@lru_cache
def get_embedder() -> Embedder:
    settings = get_settings()
    return Embedder(
        model_path=settings.embedding_model_path,
        device=settings.embedding_device,
        max_length=settings.embedding_max_length,
        normalize=settings.embedding_normalize,
    )


def is_ready() -> bool:
    """True once the singleton has been loaded (does not trigger a load)."""
    return get_embedder.cache_info().currsize > 0
