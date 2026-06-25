"""Eval gate unit tests (CLAUDE.md §10 — Eval DoD)."""

from __future__ import annotations

from pathlib import Path

import pytest
from app.core.config import get_settings
from app.eval import gate_passed, load_dataset


@pytest.fixture(autouse=True)
def _test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    get_settings.cache_clear()


def test_gate_passes_above_thresholds() -> None:
    assert gate_passed(0.8, 0.1) is True


def test_gate_passes_at_boundary() -> None:
    # threshold 0.7 → faithfulness>=0.7 and hallucination<=0.3
    assert gate_passed(0.7, 0.3) is True


def test_gate_fails_low_faithfulness() -> None:
    assert gate_passed(0.5, 0.1) is False


def test_gate_fails_high_hallucination() -> None:
    assert gate_passed(0.9, 0.5) is False


def test_load_dataset_skips_blank_lines(tmp_path: Path) -> None:
    p = tmp_path / "g.jsonl"
    p.write_text(
        '{"question": "q1", "ground_truth": "a"}\n\n{"question": "q2", "ground_truth": "b"}\n'
    )
    rows = load_dataset(str(p))
    assert len(rows) == 2
    assert rows[0]["question"] == "q1"
    assert rows[1]["ground_truth"] == "b"
