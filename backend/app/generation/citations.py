"""Citation builder (CLAUDE.md §6.12).

Resolve inline [n] markers against the numbered context list into structured
citations carrying document_id / chunk_id / char offsets / page / snippet. An
answer that asserts facts but has zero markers is flagged ungrounded by
``finalize`` (Step 9). Sentence attribution is best-effort and additive.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from app.retrieval.hybrid import Candidate

_MARKER_RE = re.compile(r"\[(\d+)\]")
_SNIPPET_LEN = 200


@dataclass
class Citation:
    marker: int
    document_id: uuid.UUID
    chunk_id: uuid.UUID
    char_start: int
    char_end: int
    page_number: int | None
    snippet: str


def _snippet(text: str) -> str:
    return text[:_SNIPPET_LEN]


def extract_markers(answer: str) -> list[int]:
    """Unique [n] markers in first-appearance order."""
    seen: dict[int, None] = {}
    for m in _MARKER_RE.finditer(answer):
        seen.setdefault(int(m.group(1)), None)
    return list(seen.keys())


def build_citations(answer: str, contexts: list[Candidate]) -> tuple[str, list[Citation]]:
    """Map every in-range [n] marker to a Citation for contexts[n-1]."""
    citations: list[Citation] = []
    for marker in extract_markers(answer):
        if 1 <= marker <= len(contexts):
            ctx = contexts[marker - 1]
            citations.append(
                Citation(
                    marker=marker,
                    document_id=ctx.document_id,
                    chunk_id=ctx.chunk_id,
                    char_start=ctx.char_start,
                    char_end=ctx.char_end,
                    page_number=ctx.page_number,
                    snippet=_snippet(ctx.content),
                )
            )
    return answer, citations


_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def attribute_sentences(answer: str, contexts: list[Candidate], embedder: object) -> list[Citation]:
    """Best-effort cosine sentence↔chunk attribution. Never blocks the response."""
    try:
        import numpy as np

        sentences = [s for s in _SENTENCE_RE.split(answer.strip()) if s.strip()]
        if not sentences or not contexts:
            return []

        encode = embedder.encode  # type: ignore[attr-defined]
        sent_vecs = np.asarray(encode(sentences, 16), dtype=np.float32)
        ctx_vecs = np.asarray(encode([c.content for c in contexts], 16), dtype=np.float32)

        out: list[Citation] = []
        for s_idx in range(len(sentences)):
            sims = ctx_vecs @ sent_vecs[s_idx]
            best = int(np.argmax(sims))
            if float(sims[best]) < 0.5:
                continue
            ctx = contexts[best]
            out.append(
                Citation(
                    marker=best + 1,
                    document_id=ctx.document_id,
                    chunk_id=ctx.chunk_id,
                    char_start=ctx.char_start,
                    char_end=ctx.char_end,
                    page_number=ctx.page_number,
                    snippet=_snippet(ctx.content),
                )
            )
        return out
    except Exception:
        return []
