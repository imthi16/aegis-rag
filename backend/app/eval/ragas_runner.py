"""RAGAS runner (CLAUDE.md §6.16).

faithfulness, answer_relevancy, context_precision, context_recall — all computed
with the LOCAL Ollama LLM + local embeddings. ragas/datasets are lazy-imported.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.eval import load_dataset
from app.eval.local_llm import get_ragas_embeddings, get_ragas_llm


@dataclass
class RagasResult:
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float
    raw: dict[str, Any] = field(default_factory=dict)


def _to_eval_record(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "question": row["question"],
        "answer": row.get("answer", ""),
        "contexts": list(row.get("contexts", [])),
        "ground_truth": row.get("ground_truth", ""),
    }


def run_ragas(dataset_path: str) -> RagasResult:
    from datasets import Dataset
    from ragas import evaluate
    from ragas.metrics import (
        answer_relevancy,
        context_precision,
        context_recall,
        faithfulness,
    )

    records = [_to_eval_record(r) for r in load_dataset(dataset_path)]
    dataset = Dataset.from_list(records)

    # Local models passed explicitly to every metric — never OpenAI.
    llm = get_ragas_llm()
    embeddings = get_ragas_embeddings()
    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=llm,
        embeddings=embeddings,
    )
    scores = dict(result)

    def _g(name: str) -> float:
        value = scores.get(name, 0.0)
        return float(value) if value is not None else 0.0

    return RagasResult(
        faithfulness=_g("faithfulness"),
        answer_relevancy=_g("answer_relevancy"),
        context_precision=_g("context_precision"),
        context_recall=_g("context_recall"),
        raw=scores,
    )
