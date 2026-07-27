"""Eval gate unit tests (CLAUDE.md §10 — Eval DoD)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from app.core.config import get_settings
from app.eval import ModelPreflight, check_local_model, gate_passed, load_dataset


@pytest.fixture(autouse=True)
def _test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    get_settings.cache_clear()


def _load_ci_gate() -> ModuleType:
    """Import repo-root eval/ci_gate.py (outside the app package) by path."""
    path = Path(__file__).resolve().parents[3] / "eval" / "ci_gate.py"
    spec = importlib.util.spec_from_file_location("aegis_ci_gate", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["aegis_ci_gate"] = module
    spec.loader.exec_module(module)
    return module


def _stub_preflight(monkeypatch: pytest.MonkeyPatch, result: ModelPreflight) -> None:
    """ci_gate imports check_local_model inside main(), so patching the
    attribute on app.eval is picked up on the next call."""
    monkeypatch.setattr("app.eval.check_local_model", lambda **_: result)


def _fake_httpx(monkeypatch: pytest.MonkeyPatch, *, tags: list[str], boom: bool) -> None:
    """Stub httpx.get so the probe never touches a real socket."""

    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return {"models": [{"name": tag} for tag in tags]}

    def _get(url: str, timeout: float | None = None) -> _Response:
        assert "/api/tags" in url
        if boom:
            raise OSError("connection refused")
        return _Response()

    import httpx

    monkeypatch.setattr(httpx, "get", _get)


@pytest.fixture
def _deps_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pretend the eval-only deps are installed (they may not be, locally)."""
    monkeypatch.setattr("app.eval._missing_eval_dependency", lambda: None)


@pytest.fixture
def _weights_ok(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    weights = tmp_path / "bge-m3"
    weights.mkdir()
    monkeypatch.setenv("EMBEDDING_MODEL_PATH", str(weights))
    get_settings.cache_clear()


# ── threshold decision ──────────────────────────────────────────────────


def test_gate_passes_above_thresholds() -> None:
    assert gate_passed(0.8, 0.1) is True


def test_gate_passes_at_boundary() -> None:
    # threshold 0.7 → faithfulness>=0.7 and hallucination<=0.3
    assert gate_passed(0.7, 0.3) is True


def test_gate_fails_low_faithfulness() -> None:
    assert gate_passed(0.5, 0.1) is False


def test_gate_fails_high_hallucination() -> None:
    assert gate_passed(0.9, 0.5) is False


# ── preflight: named skip reasons, not opaque exceptions ────────────────


def test_preflight_reports_missing_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.eval._missing_eval_dependency", lambda: "ragas")
    result = check_local_model()
    assert result.ok is False
    assert "ragas" in result.reason


@pytest.mark.usefixtures("_deps_ok")
def test_preflight_reports_missing_weights(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EMBEDDING_MODEL_PATH", str(tmp_path / "absent"))
    get_settings.cache_clear()
    result = check_local_model()
    assert result.ok is False
    assert "weights not staged" in result.reason


@pytest.mark.usefixtures("_deps_ok", "_weights_ok")
def test_preflight_reports_unreachable_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_httpx(monkeypatch, tags=[], boom=True)
    result = check_local_model()
    assert result.ok is False
    assert "unreachable" in result.reason
    # Names the host it tried, so a CI skip line is diagnosable.
    assert get_settings().ollama_host.rstrip("/") in result.reason


@pytest.mark.usefixtures("_deps_ok", "_weights_ok")
def test_preflight_reports_model_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:32b")
    get_settings.cache_clear()
    _fake_httpx(monkeypatch, tags=["llama3:8b"], boom=False)
    result = check_local_model()
    assert result.ok is False
    assert "qwen2.5:32b" in result.reason
    # Lists what IS present, so the operator can see the mismatch.
    assert "llama3:8b" in result.reason


@pytest.mark.usefixtures("_deps_ok", "_weights_ok")
def test_preflight_ok_on_exact_tag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:32b")
    get_settings.cache_clear()
    _fake_httpx(monkeypatch, tags=["qwen2.5:32b", "llama3:8b"], boom=False)
    assert check_local_model().ok is True


@pytest.mark.usefixtures("_deps_ok", "_weights_ok")
def test_preflight_ok_on_bare_name(monkeypatch: pytest.MonkeyPatch) -> None:
    # A configured name without ":tag" matches any tag of that model.
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5")
    get_settings.cache_clear()
    _fake_httpx(monkeypatch, tags=["qwen2.5:latest"], boom=False)
    assert check_local_model().ok is True


# ── gate wiring: skip and fail must not be confusable ───────────────────


def test_gate_skips_with_named_reason(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    gate = _load_ci_gate()
    reason = "Ollama unreachable at http://ollama:11434 (ConnectError)"
    _stub_preflight(monkeypatch, ModelPreflight(False, reason))

    assert gate.main(["--suite", "both"]) == 0
    err = capsys.readouterr().err
    assert "cannot evaluate" in err
    assert reason in err
    assert "SKIPPING" in err


def test_gate_fails_on_unavailable_model_when_required(monkeypatch: pytest.MonkeyPatch) -> None:
    gate = _load_ci_gate()
    _stub_preflight(monkeypatch, ModelPreflight(False, "no model"))
    assert gate.main(["--suite", "both", "--require"]) == 2


def test_gate_fails_when_eval_breaks_after_ok_preflight(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The regression the preflight exists to prevent: a broken suite must NOT be
    reported as an unprovisioned runner, even without --require."""
    gate = _load_ci_gate()
    _stub_preflight(monkeypatch, ModelPreflight(True, "model available"))

    def _boom(_dataset: str) -> object:
        raise KeyError(0)  # the exact failure shape seen in CI

    monkeypatch.setattr("app.eval.ragas_runner.run_ragas", _boom)

    assert gate.main(["--suite", "ragas"]) == 2
    err = capsys.readouterr().err
    assert "FAILED after a successful preflight" in err
    assert "SKIPPING" not in err


# ── dataset loading ─────────────────────────────────────────────────────


def test_load_dataset_skips_blank_lines(tmp_path: Path) -> None:
    p = tmp_path / "g.jsonl"
    p.write_text(
        '{"question": "q1", "ground_truth": "a"}\n\n{"question": "q2", "ground_truth": "b"}\n'
    )
    rows = load_dataset(str(p))
    assert len(rows) == 2
    assert rows[0]["question"] == "q1"
    assert rows[1]["ground_truth"] == "b"
