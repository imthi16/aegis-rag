"""CI evaluation gate (CLAUDE.md §6.16, §10 — Eval; implemented in Step 10).

Runs RAGAS + DeepEval **against local Ollama + local embeddings only** (never
OpenAI) over a golden set, writes an ``eval_runs`` row, and exits non-zero when:

    faithfulness < FAITHFULNESS_THRESHOLD
    OR hallucination_rate > (1 - FAITHFULNESS_THRESHOLD)

This Step-1 stub defines the entrypoint + exit-code contract so CI can wire it
now; the runners land in Step 10.
"""

from __future__ import annotations

import argparse
import sys

DEFAULT_DATASET = "eval/datasets/golden_qa.jsonl"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Aegis RAG CI eval gate")
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--suite", choices=["ragas", "deepeval", "both"], default="both")
    args = parser.parse_args(argv)

    # Implemented in Step 10: from eval runners wired to local models.
    print(
        f"ci_gate: not yet implemented (dataset={args.dataset}, suite={args.suite}). "
        "RAGAS + DeepEval runners land in Step 10; they MUST use local Ollama + "
        "local embeddings.",
        file=sys.stderr,
    )
    # Neutral until implemented so it can be added to CI as `continue-on-error`.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
