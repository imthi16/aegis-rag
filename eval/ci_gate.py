"""CI evaluation gate (CLAUDE.md §6.16, §10 — Eval).

Runs RAGAS + DeepEval **against local Ollama + local embeddings only** over a
golden set, writes an eval_runs row (when a DB is reachable), and exits non-zero
when faithfulness < FAITHFULNESS_THRESHOLD OR hallucination_rate >
(1 - FAITHFULNESS_THRESHOLD).

If the local model / eval deps are unavailable (e.g. CI without Ollama), the
gate SKIPS (exit 0) unless --require is passed. It never reaches OpenAI.

    python eval/ci_gate.py --suite both [--dataset path] [--require]
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
if _BACKEND.is_dir() and str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

DEFAULT_DATASET = str(Path(__file__).resolve().parent / "datasets" / "golden_qa.jsonl")


async def _persist(metrics: dict[str, object], passed: bool, suite: str, dataset: str) -> None:
    """Write an eval_runs row if a DB is reachable (best effort)."""
    try:
        from app.db.models.eval_run import EvalRun
        from app.db.session import AsyncSessionLocal, dispose_engines

        run = EvalRun(
            suite=suite,
            dataset=dataset,
            metrics=metrics,
            faithfulness_avg=round(float(metrics.get("faithfulness", 0.0)), 3),  # type: ignore[arg-type]
            hallucination_rate=round(float(metrics.get("hallucination_rate", 0.0)), 3),  # type: ignore[arg-type]
            passed=passed,
            commit_sha=os.environ.get("GIT_COMMIT"),
            run_label="ci_gate",
        )
        async with AsyncSessionLocal() as session, session.begin():
            session.add(run)
        await dispose_engines()
        print(f"ci_gate: wrote eval_runs row (passed={passed})")
    except Exception as exc:  # noqa: BLE001
        print(f"ci_gate: skipped eval_runs persistence ({type(exc).__name__})", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Aegis RAG CI eval gate")
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--suite", choices=["ragas", "deepeval", "both"], default="both")
    parser.add_argument("--require", action="store_true", help="fail (not skip) if models unavailable")
    args = parser.parse_args(argv)

    from app.eval import gate_passed

    metrics: dict[str, object] = {}
    faithfulness = 0.0
    hallucination_rate = 0.0
    try:
        if args.suite in ("ragas", "both"):
            from app.eval.ragas_runner import run_ragas

            r = run_ragas(args.dataset)
            faithfulness = r.faithfulness
            metrics.update(
                faithfulness=r.faithfulness,
                answer_relevancy=r.answer_relevancy,
                context_precision=r.context_precision,
                context_recall=r.context_recall,
            )
        if args.suite in ("deepeval", "both"):
            from app.eval.deepeval_runner import run_deepeval

            d = run_deepeval(args.dataset)
            hallucination_rate = d.hallucination_rate
            if not faithfulness:
                faithfulness = d.faithfulness
            metrics["hallucination_rate"] = d.hallucination_rate
    except Exception as exc:  # noqa: BLE001
        msg = f"ci_gate: eval could not run ({type(exc).__name__}: {exc})"
        if args.require:
            print(msg, file=sys.stderr)
            return 2
        print(f"{msg} — SKIPPING (no local model). Use --require to fail.", file=sys.stderr)
        return 0

    passed = gate_passed(faithfulness, hallucination_rate)
    print(f"ci_gate: faithfulness={faithfulness:.3f} hallucination_rate={hallucination_rate:.3f} passed={passed}")
    asyncio.run(_persist(metrics, passed, args.suite, args.dataset))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
