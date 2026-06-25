"""Token-aware recursive chunker (CLAUDE.md §6.4).

Splits on paragraph → sentence → word boundaries, packing segments into chunks
of ~size_tokens with overlap_tokens overlap, preserving exact char offsets into
the normalized source text and the source page number.

Token counting uses the local BGE-M3 tokenizer loaded offline from
EMBEDDING_MODEL_PATH when available; otherwise a deterministic unicode word
tokenizer (offline, never tiktoken/network).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from app.core.config import get_settings
from app.ingestion.parsers import PageSpan, ParsedDoc

_PARA_RE = re.compile(r"\n\s*\n")
_SENT_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_RE = re.compile(r"\S+")
_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


@dataclass
class Chunk:
    index: int
    content: str
    token_count: int
    char_start: int
    char_end: int
    page_number: int | None


@lru_cache
def _tokenizer() -> Any | None:
    try:
        from transformers import AutoTokenizer  # lazy; offline

        return AutoTokenizer.from_pretrained(
            get_settings().embedding_model_path, local_files_only=True
        )
    except Exception:
        return None


def count_tokens(text: str) -> int:
    tok = _tokenizer()
    if tok is not None:
        return len(tok.encode(text, add_special_tokens=False))
    return len(_TOKEN_RE.findall(text))


def _split(text: str, start: int, end: int, sep: re.Pattern[str]) -> list[tuple[int, int]]:
    """Content spans within [start, end) separated by ``sep``, dropping blanks."""
    spans: list[tuple[int, int]] = []
    pos = start
    for m in sep.finditer(text, start, end):
        if m.start() > pos:
            spans.append((pos, m.start()))
        pos = m.end()
    if pos < end:
        spans.append((pos, end))
    return [(s, e) for s, e in spans if text[s:e].strip()]


def _window_words(text: str, start: int, end: int, size: int) -> list[tuple[int, int]]:
    """Last resort: pack words into <= size-token windows (offset-exact)."""
    words = [(m.start(), m.end()) for m in _WORD_RE.finditer(text, start, end)]
    if not words:
        return []
    windows: list[tuple[int, int]] = []
    win_start = words[0][0]
    count = 0
    last_end = words[0][1]
    for ws, we in words:
        count += 1
        if count > size and last_end > win_start:
            windows.append((win_start, last_end))
            win_start = ws
            count = 1
        last_end = we
    windows.append((win_start, last_end))
    return windows


def _leaf_segments(text: str, size: int) -> list[tuple[int, int]]:
    segs: list[tuple[int, int]] = []
    for ps, pe in _split(text, 0, len(text), _PARA_RE):
        if count_tokens(text[ps:pe]) <= size:
            segs.append((ps, pe))
            continue
        for ss, se in _split(text, ps, pe, _SENT_RE):
            if count_tokens(text[ss:se]) <= size:
                segs.append((ss, se))
            else:
                segs.extend(_window_words(text, ss, se, size))
    return segs


def _page_for_offset(pages: list[PageSpan], offset: int) -> int | None:
    page_number: int | None = None
    for span in pages:
        if span.char_start <= offset:
            page_number = span.page_number
        else:
            break
    return page_number


def _tail_overlap(text: str, segs: list[tuple[int, int]], overlap: int) -> list[tuple[int, int]]:
    if overlap <= 0:
        return []
    acc: list[tuple[int, int]] = []
    toks = 0
    for s, e in reversed(segs):
        t = count_tokens(text[s:e])
        if acc and toks + t > overlap:
            break
        acc.append((s, e))
        toks += t
    return list(reversed(acc))


def chunk_text(parsed: ParsedDoc, size_tokens: int, overlap_tokens: int) -> list[Chunk]:
    text = parsed.text
    if not text.strip():
        return []

    segs = _leaf_segments(text, size_tokens)
    chunks: list[Chunk] = []
    current: list[tuple[int, int]] = []
    current_tokens = 0

    def emit() -> None:
        if not current:
            return
        char_start = current[0][0]
        char_end = current[-1][1]
        content = text[char_start:char_end]
        chunks.append(
            Chunk(
                index=len(chunks),
                content=content,
                token_count=count_tokens(content),
                char_start=char_start,
                char_end=char_end,
                page_number=_page_for_offset(parsed.pages, char_start),
            )
        )

    for seg in segs:
        seg_tokens = count_tokens(text[seg[0] : seg[1]])
        if current and current_tokens + seg_tokens > size_tokens:
            emit()
            current = _tail_overlap(text, current, overlap_tokens)
            current_tokens = sum(count_tokens(text[s:e]) for s, e in current)
        current.append(seg)
        current_tokens += seg_tokens

    emit()
    return chunks
