"""RRF unit tests (CLAUDE.md §10 — Hybrid DoD).

Must match the reference reciprocal_rank_fusion exactly.
"""

from __future__ import annotations

from app.retrieval.rrf import reciprocal_rank_fusion


def test_reference_scores_and_ordering() -> None:
    result = reciprocal_rank_fusion([[1, 2, 3], [2, 3, 1]], k=60)
    scores = dict(result)
    expected = {
        1: 1 / 61 + 1 / 63,
        2: 1 / 62 + 1 / 61,
        3: 1 / 63 + 1 / 62,
    }
    for doc_id, value in expected.items():
        assert abs(scores[doc_id] - value) < 1e-12
    # id 2 has the highest combined reciprocal rank.
    assert result[0][0] == 2
    assert [doc_id for doc_id, _ in result] == sorted(scores, key=lambda d: -scores[d])


def test_single_list_is_monotonic() -> None:
    result = reciprocal_rank_fusion([[5, 6, 7]], k=60)
    assert [doc_id for doc_id, _ in result] == [5, 6, 7]
    assert abs(result[0][1] - 1 / 61) < 1e-12


def test_empty_inputs() -> None:
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[]]) == []


def test_k_changes_scores() -> None:
    assert abs(dict(reciprocal_rank_fusion([[1]], k=60))[1] - 1 / 61) < 1e-12
    assert abs(dict(reciprocal_rank_fusion([[1]], k=10))[1] - 1 / 11) < 1e-12
