"""Prompt templates (CLAUDE.md §6.11).

Generation answers ONLY from the numbered contexts, cites inline as [n], and
falls back to the exact insufficient-evidence sentence — never outside
knowledge. Grading prompts force JSON and run at temperature 0.0.
"""

from __future__ import annotations

from app.retrieval.hybrid import Candidate

INSUFFICIENT_EVIDENCE = "I don't have enough information in the provided sources to answer that."

_GENERATION_SYSTEM = (
    "You are Aegis, a sovereign RAG assistant for regulated industries. "
    "Answer the user's question using ONLY the numbered context passages provided. "
    "Cite every factual claim inline using the bracketed index of the supporting "
    "passage, e.g. [1] or [2]. Do not use any outside knowledge. If the contexts "
    "do not contain enough information to answer, reply with exactly: "
    f'"{INSUFFICIENT_EVIDENCE}" and nothing else.'
)


def _format_contexts(contexts: list[Candidate]) -> str:
    blocks = []
    for i, c in enumerate(contexts, start=1):
        blocks.append(f"[{i}] {c.content}")
    return "\n\n".join(blocks) if blocks else "(no context provided)"


def generation_prompt(query: str, contexts: list[Candidate]) -> list[dict[str, str]]:
    user = (
        f"Context passages:\n\n{_format_contexts(contexts)}\n\n"
        f"Question: {query}\n\n"
        "Answer using only the passages above, with inline [n] citations."
    )
    return [
        {"role": "system", "content": _GENERATION_SYSTEM},
        {"role": "user", "content": user},
    ]


def doc_relevance_prompt(query: str, context: str) -> list[dict[str, str]]:
    system = (
        "You grade whether a context passage is relevant to a question. "
        'Respond ONLY with JSON of the form {"relevant": <true|false>, '
        '"score": <number between 0 and 1>}. No prose.'
    )
    user = f"Question: {query}\n\nPassage:\n{context}\n\nIs this passage relevant?"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def query_rewrite_prompt(query: str, reason: str) -> list[dict[str, str]]:
    system = (
        "You rewrite a search query to improve retrieval over a private document "
        "corpus. Output ONLY the rewritten query on a single line, no quotes, no "
        "explanation. Never invent facts."
    )
    user = f"Original query: {query}\nReason retrieval was weak: {reason}\nRewritten query:"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def faithfulness_prompt(answer: str, contexts: list[Candidate]) -> list[dict[str, str]]:
    system = (
        "You verify whether an answer is fully supported by the provided context "
        "passages (faithfulness / no hallucination). Respond ONLY with JSON of the "
        'form {"faithful": <true|false>, "score": <number between 0 and 1>, '
        '"unsupported_claims": [<string>, ...]}. A claim is unsupported if it is '
        "not entailed by any passage."
    )
    user = (
        f"Context passages:\n\n{_format_contexts(contexts)}\n\n"
        f"Answer to verify:\n{answer}\n\n"
        "Return the JSON verdict."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
