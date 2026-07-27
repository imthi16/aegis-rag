"""Built-in local evaluator (CLAUDE.md §6.16 — replaces the deepeval package).

The grader is injected so these run offline with no Ollama server.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.eval.deepeval_runner import DeepEvalResult, _parse_score, run_deepeval
from app.eval.local_llm import Grader


def test_parse_score_clamps_and_handles_bad_json() -> None:
    assert _parse_score('{"score": 0.5}', "score") == 0.5
    assert _parse_score('{"score": 1.7}', "score") == 1.0  # clamped high
    assert _parse_score('{"score": -2}', "score") == 0.0  # clamped low
    assert _parse_score("not json at all", "score") == 0.0
    assert _parse_score('{"other": 1}', "score") == 0.0  # missing key
    assert _parse_score("[1, 2, 3]", "score") == 0.0  # not an object
    assert _parse_score('{"score": "oops"}', "score") == 0.0  # non-numeric


def _write_dataset(tmp_path: Path, n: int) -> str:
    ds = tmp_path / "golden.jsonl"
    ds.write_text(
        "\n".join(
            json.dumps({"question": "q", "answer": "a", "contexts": ["c"]}) for _ in range(n)
        ),
        encoding="utf-8",
    )
    return str(ds)


def test_run_deepeval_aggregates_with_injected_grader(tmp_path: Path) -> None:
    dataset = _write_dataset(tmp_path, n=2)

    # Route each metric by its system prompt so we can assert distinct means.
    def fake_grader(messages: list[dict[str, str]]) -> str:
        system = messages[0]["content"].lower()
        if "faithful" in system:
            return json.dumps({"score": 0.8})
        if "hallucinat" in system:
            return json.dumps({"score": 0.1})
        return json.dumps({"score": 0.9})

    grader: Grader = fake_grader
    result = run_deepeval(dataset, grader=grader)

    assert isinstance(result, DeepEvalResult)
    assert result.faithfulness == 0.8
    assert result.hallucination_rate == 0.1
    assert result.answer_relevancy == 0.9
    assert result.raw["n"] == 2


def test_run_deepeval_empty_dataset_returns_zeros(tmp_path: Path) -> None:
    ds = tmp_path / "empty.jsonl"
    ds.write_text("", encoding="utf-8")
    result = run_deepeval(str(ds), grader=lambda _messages: '{"score": 1}')
    assert result.faithfulness == 0.0
    assert result.hallucination_rate == 0.0
    assert result.answer_relevancy == 0.0
