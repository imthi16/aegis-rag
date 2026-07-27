"""Citation builder unit tests (CLAUDE.md §10 — Generation + citations DoD)."""

from __future__ import annotations

import uuid

from app.generation.citations import build_citations, extract_markers
from app.retrieval.hybrid import Candidate


def _ctx(content: str) -> Candidate:
    return Candidate(
        faiss_id=1,
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        content=content,
        char_start=10,
        char_end=10 + len(content),
        page_number=3,
        score=0.5,
    )


def test_markers_resolve_to_citations_with_offsets() -> None:
    c1, c2 = _ctx("alpha content"), _ctx("beta content")
    _, cits = build_citations("Alpha [1] and beta [2].", [c1, c2])
    assert [c.marker for c in cits] == [1, 2]
    assert cits[0].document_id == c1.document_id
    assert cits[0].chunk_id == c1.chunk_id
    assert (cits[0].char_start, cits[0].char_end) == (c1.char_start, c1.char_end)
    assert cits[0].page_number == 3
    assert cits[0].snippet == "alpha content"


def test_no_markers_yields_no_citations() -> None:
    _, cits = build_citations("No citations here.", [_ctx("x")])
    assert cits == []


def test_out_of_range_marker_ignored() -> None:
    _, cits = build_citations("ref [5] only", [_ctx("x")])
    assert cits == []


def test_duplicate_markers_deduped() -> None:
    _, cits = build_citations("foo [1] bar [1]", [_ctx("a")])
    assert len(cits) == 1
    assert cits[0].marker == 1


def test_snippet_truncated_to_200() -> None:
    _, cits = build_citations("see [1]", [_ctx("z" * 500)])
    assert len(cits[0].snippet) == 200


def test_extract_markers_order_and_dedupe() -> None:
    assert extract_markers("a [2] b [1] c [2] d [3]") == [2, 1, 3]
