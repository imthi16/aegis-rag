"""Built-in local evaluator (CLAUDE.md §6.16 — replaces the deepeval package).

CLAUDE.md named DeepEval, but importing the ``deepeval`` package pulls in a
telemetry/tracking layer and cloud-model backends (it eagerly imports
``google.genai``), which violates Golden Rule 1 (ZERO EGRESS) and crashes when
offline. This module computes the same hallucination / faithfulness /
answer-relevancy signals entirely from the LOCAL Ollama model via JSON grading
prompts at temperature 0 — no third-party eval package, no network.

The public names (``run_deepeval``, ``DeepEvalResult``) and the
"deepeval"/"both" suite labels are kept for API / CI / frontend compatibility;
only the implementation changed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from app.eval import load_dataset
from app.eval.local_llm import Grader, get_local_grader


@dataclass
class DeepEvalResult:
    hallucination_rate: float
    faithfulness: float
    answer_relevancy: float
    raw: dict[str, Any] = field(default_factory=dict)


def _clamp01(value: Any) -> float:
    """Coerce a model-supplied value to a float in [0, 1]; bad input -> 0.0."""
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, score))


def _parse_score(raw: str, key: str) -> float:
    """Parse a JSON grader reply and return the clamped [0,1] score for ``key``."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return 0.0
    if not isinstance(data, dict):
        return 0.0
    return _clamp01(data.get(key, 0.0))


def _format_contexts(contexts: list[str]) -> str:
    blocks = [f"[{i}] {c}" for i, c in enumerate(contexts, start=1)]
    return "\n\n".join(blocks) if blocks else "(no context provided)"


def _faithfulness_prompt(answer: str, contexts: list[str]) -> list[dict[str, str]]:
    system = (
        "You grade the FAITHFULNESS of an answer against its supporting context "
        "passages. An answer is faithful when every factual claim it makes is "
        "entailed by the passages. Respond ONLY with JSON of the form "
        '{"score": <number 0..1>, "unsupported_claims": [<string>, ...]}. '
        "score is the fraction of the answer's claims that are supported by the "
        "passages (1.0 = all supported, 0.0 = none). No prose."
    )
    user = (
        f"Context passages:\n\n{_format_contexts(contexts)}\n\n"
        f"Answer:\n{answer}\n\nReturn the JSON verdict."
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _hallucination_prompt(answer: str, contexts: list[str]) -> list[dict[str, str]]:
    system = (
        "You measure HALLUCINATION: the degree to which an answer asserts "
        "information that contradicts, or is not supported by, the context "
        "passages. Respond ONLY with JSON of the form "
        '{"score": <number 0..1>, "hallucinated_claims": [<string>, ...]}. '
        "score is the fraction of the answer that is fabricated or contradicted "
        "(0.0 = fully grounded, 1.0 = entirely fabricated). No prose."
    )
    user = (
        f"Context passages:\n\n{_format_contexts(contexts)}\n\n"
        f"Answer:\n{answer}\n\nReturn the JSON verdict."
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _relevancy_prompt(question: str, answer: str) -> list[dict[str, str]]:
    system = (
        "You grade ANSWER RELEVANCY: how directly an answer addresses the "
        "question asked, independent of factual correctness. Respond ONLY with "
        'JSON of the form {"score": <number 0..1>} where 1.0 fully addresses the '
        "question and 0.0 is unrelated. No prose."
    )
    user = f"Question: {question}\n\nAnswer:\n{answer}\n\nReturn the JSON verdict."
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def run_deepeval(dataset_path: str, grader: Grader | None = None) -> DeepEvalResult:
    """Score the golden set with the local model.

    Each row is graded for faithfulness, hallucination and answer-relevancy with
    a JSON prompt at temperature 0; the corpus result is the per-metric mean.
    ``grader`` is injectable so tests can run without a live Ollama server.
    """
    grade = grader or get_local_grader()
    rows = load_dataset(dataset_path)
    if not rows:
        return DeepEvalResult(hallucination_rate=0.0, faithfulness=0.0, answer_relevancy=0.0)

    faithfulness_scores: list[float] = []
    hallucination_scores: list[float] = []
    relevancy_scores: list[float] = []

    for row in rows:
        question = str(row.get("question", ""))
        answer = str(row.get("answer", ""))
        contexts = [str(c) for c in row.get("contexts", [])]

        faithfulness_scores.append(
            _parse_score(grade(_faithfulness_prompt(answer, contexts)), "score")
        )
        hallucination_scores.append(
            _parse_score(grade(_hallucination_prompt(answer, contexts)), "score")
        )
        relevancy_scores.append(_parse_score(grade(_relevancy_prompt(question, answer)), "score"))

    faithfulness = _mean(faithfulness_scores)
    hallucination_rate = _mean(hallucination_scores)
    answer_relevancy = _mean(relevancy_scores)
    return DeepEvalResult(
        hallucination_rate=hallucination_rate,
        faithfulness=faithfulness,
        answer_relevancy=answer_relevancy,
        raw={
            "faithfulness": faithfulness,
            "hallucination_rate": hallucination_rate,
            "answer_relevancy": answer_relevancy,
            "n": len(rows),
        },
    )
