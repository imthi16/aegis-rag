"""Embedder unit test (CLAUDE.md §10 — Embeddings DoD).

Requires the pre-staged BGE-M3 weights + FlagEmbedding/torch. Skips cleanly when
they are absent (air-gapped dev box) so the rest of the suite still runs.
"""

from __future__ import annotations

import os

import numpy as np
import pytest
from app.core.config import get_settings

settings = get_settings()
_HAS_WEIGHTS = os.path.isdir(settings.embedding_model_path)
try:
    import FlagEmbedding  # noqa: F401

    _HAS_FLAG = True
except Exception:
    _HAS_FLAG = False

pytestmark = pytest.mark.skipif(
    not (_HAS_WEIGHTS and _HAS_FLAG),
    reason="BGE-M3 weights / FlagEmbedding not available in this environment",
)


def test_encode_shape_and_normalization() -> None:
    from app.embeddings.embedder import get_embedder

    emb = get_embedder()
    vecs = emb.encode(["hello world", "second text"], batch_size=2)
    assert vecs.shape == (2, settings.embedding_dim)
    assert vecs.dtype == np.float32
    norms = np.linalg.norm(vecs, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-3)


def test_encode_query_is_1d() -> None:
    from app.embeddings.embedder import get_embedder

    v = get_embedder().encode_query("a single query")
    assert v.shape == (settings.embedding_dim,)
