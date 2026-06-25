"""DeepEval runner (CLAUDE.md §6.16).

hallucination, faithfulness, answer_relevancy — all computed with the LOCAL
Ollama model (DeepEval defaults to OpenAI; we override). Lazy-imported.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.eval import load_dataset
from app.eval.local_llm import get_deepeval_model


@dataclass
class DeepEvalResult:
    hallucination_rate: float
    faithfulness: float
    answer_relevancy: float
    raw: dict[str, Any] = field(default_factory=dict)


def run_deepeval(dataset_path: str) -> DeepEvalResult:
    from deepeval import evaluate
    from deepeval.metrics import (
        AnswerRelevancyMetric,
        FaithfulnessMetric,
        HallucinationMetric,
    )
    from deepeval.test_case import LLMTestCase

    model = get_deepeval_model()
    rows = load_dataset(dataset_path)

    cases = [
        LLMTestCase(
            input=row["question"],
            actual_output=row.get("answer", ""),
            context=list(row.get("contexts", [])),
            retrieval_context=list(row.get("contexts", [])),
        )
        for row in rows
    ]

    hallucination = HallucinationMetric(model=model)
    faithfulness = FaithfulnessMetric(model=model)
    answer_relevancy = AnswerRelevancyMetric(model=model)
    results = evaluate(cases, metrics=[hallucination, faithfulness, answer_relevancy])

    # Aggregate mean metric scores across cases.
    agg = _aggregate(results)
    return DeepEvalResult(
        hallucination_rate=agg.get("Hallucination", 0.0),
        faithfulness=agg.get("Faithfulness", 0.0),
        answer_relevancy=agg.get("Answer Relevancy", 0.0),
        raw=agg,
    )


def _aggregate(results: Any) -> dict[str, float]:
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    test_results = getattr(results, "test_results", results)
    for case in test_results:
        for metric in getattr(case, "metrics_data", []) or []:
            name = getattr(metric, "name", "")
            score = float(getattr(metric, "score", 0.0) or 0.0)
            sums[name] = sums.get(name, 0.0) + score
            counts[name] = counts.get(name, 0) + 1
    return {name: sums[name] / counts[name] for name in sums if counts[name]}
