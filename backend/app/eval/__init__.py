"""Evaluation package (CLAUDE.md §6.16).

Shared helpers: golden dataset loader + the CI gate decision. RAGAS/DeepEval are
ALWAYS wired to the local Ollama + local embeddings (never OpenAI) — see
local_llm.py.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import get_settings


def load_dataset(path: str) -> list[dict[str, Any]]:
    """Load a golden_qa.jsonl file → list of records."""
    rows: list[dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def gate_passed(faithfulness: float, hallucination_rate: float) -> bool:
    """CI gate decision (§6.16).

    Passes iff faithfulness >= FAITHFULNESS_THRESHOLD AND
    hallucination_rate <= (1 - FAITHFULNESS_THRESHOLD).
    """
    threshold = get_settings().faithfulness_threshold
    return faithfulness >= threshold and hallucination_rate <= (1.0 - threshold)
