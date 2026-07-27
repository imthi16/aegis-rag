"""Evaluation package (CLAUDE.md §6.16).

Shared helpers: golden dataset loader, the local-model preflight probe, and the
CI gate decision. RAGAS/DeepEval are ALWAYS wired to the local Ollama + local
embeddings (never OpenAI) — see local_llm.py.
"""

from __future__ import annotations

import importlib.util
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import get_settings

# Eval-only imports. Absent in a lean install, so the gate must report their
# absence as "cannot evaluate here" rather than crashing mid-run.
_EVAL_DEPENDENCIES = ("ragas", "langchain_community", "ollama")

_PROBE_TIMEOUT_S = 5.0


def load_dataset(path: str) -> list[dict[str, Any]]:
    """Load a golden_qa.jsonl file → list of records."""
    rows: list[dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


@dataclass(frozen=True)
class ModelPreflight:
    """Outcome of ``check_local_model``.

    ``ok`` False means *this environment cannot evaluate* — a legitimate skip.
    ``reason`` is always human-readable and names the specific blocker, so a CI
    skip line says what was missing instead of leaking an opaque exception.
    """

    ok: bool
    reason: str


def _missing_eval_dependency() -> str | None:
    """First eval-only dependency that is not importable, else None."""
    for module in _EVAL_DEPENDENCIES:
        try:
            if importlib.util.find_spec(module) is None:
                return module
        except (ImportError, ValueError):
            return module
    return None


def _model_present(available: list[str], wanted: str) -> bool:
    """Is ``wanted`` among Ollama's tag names?

    An exact match wins. A bare name with no ``:tag`` (``qwen2.5``) also matches
    any tag of that model (``qwen2.5:latest``), mirroring how Ollama resolves it.
    """
    if wanted in available:
        return True
    if ":" not in wanted:
        return any(tag.split(":", 1)[0] == wanted for tag in available)
    return False


def check_local_model(*, timeout_s: float = _PROBE_TIMEOUT_S) -> ModelPreflight:
    """Probe the LOCAL Ollama server + staged embedding weights before evaluating.

    This exists to separate "this runner has no local model" (skip, exit 0) from
    "evaluation is broken" (fail). Without it every metric job dies on a
    connection error and the gate surfaces one confusing exception, so an
    unprovisioned runner and a genuine regression look identical.

    Only ever contacts ``OLLAMA_HOST`` — a service name inside the compose
    network — and never any external host (Golden Rule 1).
    """
    settings = get_settings()

    missing = _missing_eval_dependency()
    if missing is not None:
        return ModelPreflight(False, f"eval dependency '{missing}' is not installed")

    # RAGAS scores against the local BGE-M3; without the weights it cannot run.
    if not Path(settings.embedding_model_path).is_dir():
        return ModelPreflight(
            False, f"embedding weights not staged at {settings.embedding_model_path}"
        )

    host = settings.ollama_host.rstrip("/")
    try:
        import httpx

        response = httpx.get(f"{host}/api/tags", timeout=timeout_s)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:  # noqa: BLE001 — unreachable local server, any cause
        return ModelPreflight(False, f"Ollama unreachable at {host} ({type(exc).__name__})")

    tags = [str(entry.get("name", "")) for entry in payload.get("models", [])]
    if not _model_present(tags, settings.ollama_model):
        available = ", ".join(sorted(tag for tag in tags if tag)) or "none"
        return ModelPreflight(
            False,
            f"model '{settings.ollama_model}' not on {host} (available: {available})",
        )

    return ModelPreflight(True, f"model '{settings.ollama_model}' available at {host}")


def gate_passed(faithfulness: float, hallucination_rate: float) -> bool:
    """CI gate decision (§6.16).

    Passes iff faithfulness >= FAITHFULNESS_THRESHOLD AND
    hallucination_rate <= (1 - FAITHFULNESS_THRESHOLD).
    """
    threshold = get_settings().faithfulness_threshold
    return faithfulness >= threshold and hallucination_rate <= (1.0 - threshold)
