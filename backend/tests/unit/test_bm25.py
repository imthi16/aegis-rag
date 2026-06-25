"""BM25 index unit tests (CLAUDE.md §10 — Embeddings/FAISS/BM25 DoD).

search returns faiss_ids ranked; allowed_faiss_ids RBAC filter honored;
save/load persists across a fresh instance.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app.core.config import get_settings
from app.retrieval.bm25_index import BM25Index, tokenize

CORPUS = [
    (1, "the quick brown fox"),
    (2, "lazy dog sleeps all day"),
    (3, "quick brown dog runs"),
]


def test_tokenize_is_lowercase_word_split() -> None:
    assert tokenize("The Quick, Brown FOX!") == ["the", "quick", "brown", "fox"]


def test_search_ranks_relevant_ids_first() -> None:
    idx = BM25Index()
    idx.build(CORPUS)
    results = idx.search("quick brown", top_k=3)
    ids = [fid for fid, _ in results]
    # Docs 1 and 3 contain both terms; doc 2 contains neither.
    assert set(ids[:2]) == {1, 3}
    assert results[0][1] >= results[-1][1]


def test_rbac_filter_restricts_results() -> None:
    idx = BM25Index()
    idx.build(CORPUS)
    results = idx.search("quick brown dog", top_k=3, allowed_faiss_ids={2})
    assert {fid for fid, _ in results} == {2}


def test_empty_allowed_set_returns_nothing() -> None:
    idx = BM25Index()
    idx.build(CORPUS)
    assert idx.search("quick", top_k=3, allowed_faiss_ids=set()) == []


def test_add_then_search_includes_new_doc() -> None:
    idx = BM25Index()
    idx.build(CORPUS)
    idx.add([(4, "fox jumps over quick brown")])
    ids = {fid for fid, _ in idx.search("fox", top_k=5)}
    assert 4 in ids


def test_save_and_load_persists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("BM25_INDEX_PATH", str(tmp_path / "bm25.pkl"))
    get_settings.cache_clear()

    idx = BM25Index()
    idx.build(CORPUS)
    idx.save()

    reopened = BM25Index()
    reopened.load()
    assert reopened.size == 3
    ids = {fid for fid, _ in reopened.search("quick brown", top_k=2)}
    assert ids == {1, 3}
