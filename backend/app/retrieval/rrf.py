"""Reciprocal Rank Fusion (CLAUDE.md §6.8).

Pure, deterministic, rank-only fusion — robust to incomparable score scales
(BM25 vs cosine). This implementation matches the reference exactly.
"""

from __future__ import annotations


def reciprocal_rank_fusion(
    ranked_lists: list[list[int]],  # each is faiss_ids ordered best->worst
    k: int = 60,
) -> list[tuple[int, float]]:
    scores: dict[int, float] = {}
    for ranked in ranked_lists:
        for rank, doc_id in enumerate(ranked):  # rank starts at 0
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
