"""Chunker unit tests (CLAUDE.md §10 — Ingestion DoD).

Chunks have monotonic char_start<char_end, content matching the source slice,
correct page numbers, and positive token counts. Uses the offline fallback
tokenizer when BGE-M3 weights are absent.
"""

from __future__ import annotations

from app.ingestion.chunker import chunk_text
from app.ingestion.parsers import PageSpan, ParsedDoc


def _doc(text: str, pages: list[PageSpan] | None = None) -> ParsedDoc:
    return ParsedDoc(
        text=text,
        pages=pages or [PageSpan(1, 0, len(text))],
        content_hash="x",
    )


def test_chunks_have_valid_offsets_and_content() -> None:
    text = ("Para one has several words here. " * 5) + "\n\n" + ("Para two also words. " * 5)
    chunks = chunk_text(_doc(text), size_tokens=10, overlap_tokens=2)
    assert len(chunks) >= 2
    for c in chunks:
        assert 0 <= c.char_start < c.char_end <= len(text)
        assert c.content == text[c.char_start : c.char_end]
        assert c.token_count > 0
        assert c.page_number == 1
    assert [c.index for c in chunks] == list(range(len(chunks)))
    # Chunks are emitted in source order.
    assert [c.char_start for c in chunks] == sorted(c.char_start for c in chunks)


def test_empty_text_yields_no_chunks() -> None:
    assert chunk_text(_doc("   \n\n   "), size_tokens=10, overlap_tokens=2) == []


def test_page_number_mapping_across_two_pages() -> None:
    p1 = "alpha beta gamma delta. " * 3
    p2 = "epsilon zeta eta theta. " * 3
    text = p1 + "\n" + p2
    pages = [PageSpan(1, 0, len(p1)), PageSpan(2, len(p1) + 1, len(text))]
    chunks = chunk_text(_doc(text, pages), size_tokens=6, overlap_tokens=0)
    page_nums = {c.page_number for c in chunks}
    assert 2 in page_nums
    assert page_nums <= {1, 2}


def test_large_size_yields_single_chunk() -> None:
    text = "just a short paragraph with a few tokens."
    chunks = chunk_text(_doc(text), size_tokens=512, overlap_tokens=64)
    assert len(chunks) == 1
    assert chunks[0].content == text
