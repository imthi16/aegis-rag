"""Cross-encoder reranker (CLAUDE.md §6.10).

bge-reranker-v2-m3 via FlagReranker, loaded once from a pre-staged offline path.
Scores each (query, candidate) pair, sorts desc, attaches the rerank score to
Candidate.score, and truncates to top_n. The heavy import is lazy so this module
loads without the weights present.
"""

from __future__ import annotations

import os
from functools import lru_cache

from app.core.config import get_settings
from app.retrieval.hybrid import Candidate


def rerank_by_scores(
    candidates: list[Candidate], scores: list[float], top_n: int
) -> list[Candidate]:
    """Pure: attach scores, sort desc, truncate to top_n (testable without weights)."""
    for cand, score in zip(candidates, scores, strict=True):
        cand.score = float(score)
    ordered = sorted(candidates, key=lambda c: c.score, reverse=True)
    return ordered[:top_n]


class Reranker:
    def __init__(self, model_path: str, device: str, use_fp16: bool) -> None:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        from FlagEmbedding import FlagReranker  # lazy heavy import

        self.batch_size = get_settings().reranker_batch_size
        self._model = FlagReranker(model_path, use_fp16=use_fp16, devices=device)

    def rerank(self, query: str, candidates: list[Candidate], top_n: int) -> list[Candidate]:
        if not candidates:
            return []
        pairs = [[query, c.content] for c in candidates]
        raw = self._model.compute_score(pairs, batch_size=self.batch_size, normalize=True)
        scores = [float(s) for s in (raw if isinstance(raw, list) else [raw])]
        return rerank_by_scores(candidates, scores, top_n)


@lru_cache
def get_reranker() -> Reranker:
    settings = get_settings()
    return Reranker(
        model_path=settings.reranker_model_path,
        device=settings.reranker_device,
        use_fp16=settings.reranker_use_fp16,
    )


def is_ready() -> bool:
    """True once the singleton has been loaded (does not trigger a load)."""
    return get_reranker.cache_info().currsize > 0
