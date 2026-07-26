"""Eval routes (CLAUDE.md §7 Eval). Role: admin only.

POST /eval/run        run RAGAS/DeepEval (local models) and persist an eval_runs row
GET  /eval/runs       list runs
GET  /eval/runs/{id}  run detail
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.logger import write_audit
from app.core.config import get_settings
from app.core.dependencies import get_db, require_roles
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.db.models.eval_run import EvalRun
from app.db.models.user import User
from app.db.session import AsyncSessionLocal
from app.eval import gate_passed
from app.eval.deepeval_runner import run_deepeval
from app.eval.ragas_runner import run_ragas
from app.rbac.classifications import Role
from app.schemas.eval import (
    EvalRunCreated,
    EvalRunDetail,
    EvalRunListResponse,
    EvalRunRequest,
    EvalRunSummary,
)
from app.schemas.pagination import Pagination, pagination_params

router = APIRouter(prefix="/eval", tags=["eval"])

logger = get_logger("app.eval")

_admin = require_roles(Role.ADMIN)

# Run lifecycle, carried in the eval_runs.metrics JSONB so no migration is needed
# to distinguish "still running" from "finished and failed the gate".
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"


def _default_dataset() -> str:
    from app.eval import __file__ as eval_init

    return str(Path(eval_init).parent / "datasets" / "golden_qa.jsonl")


def _execute_suites(suite: str, dataset: str) -> dict[str, Any]:
    """Run the requested suites. Blocking + CPU/LLM-bound — never call on the loop.

    Returns the fields to persist onto the ``eval_runs`` row.
    """
    metrics: dict[str, Any] = {}
    faithfulness: float | None = None
    answer_relevancy: float | None = None
    context_precision: float | None = None
    hallucination_rate: float | None = None

    if suite in ("ragas", "both"):
        r = run_ragas(dataset)
        faithfulness = r.faithfulness
        answer_relevancy = r.answer_relevancy
        context_precision = r.context_precision
        metrics["ragas"] = {
            "faithfulness": r.faithfulness,
            "answer_relevancy": r.answer_relevancy,
            "context_precision": r.context_precision,
            "context_recall": r.context_recall,
        }

    if suite in ("deepeval", "both"):
        d = run_deepeval(dataset)
        hallucination_rate = d.hallucination_rate
        faithfulness = faithfulness if faithfulness is not None else d.faithfulness
        answer_relevancy = answer_relevancy if answer_relevancy is not None else d.answer_relevancy
        metrics["deepeval"] = {
            "hallucination_rate": d.hallucination_rate,
            "faithfulness": d.faithfulness,
            "answer_relevancy": d.answer_relevancy,
        }

    faithfulness_val = faithfulness or 0.0
    hallucination_val = hallucination_rate if hallucination_rate is not None else 0.0
    metrics["status"] = STATUS_COMPLETED
    return {
        "metrics": metrics,
        "faithfulness_avg": round(faithfulness_val, 3),
        "answer_relevancy_avg": (
            round(answer_relevancy, 3) if answer_relevancy is not None else None
        ),
        "context_precision_avg": (
            round(context_precision, 3) if context_precision is not None else None
        ),
        "hallucination_rate": round(hallucination_val, 3),
        "passed": gate_passed(faithfulness_val, hallucination_val),
    }


async def _run_eval_in_background(run_id: uuid.UUID, suite: str, dataset: str) -> None:
    """Execute the suites off the event loop and record the outcome on the row.

    Opens its own session: the request's session is closed once the 202 is
    returned. A failure is recorded on the row (``status: failed``) rather than
    left as a run that is "running" forever.
    """
    try:
        fields = await asyncio.to_thread(_execute_suites, suite, dataset)
    except Exception as exc:
        logger.error("eval_run_failed", run_id=str(run_id), error_type=type(exc).__name__)
        fields = {
            "metrics": {"status": STATUS_FAILED, "error_type": type(exc).__name__},
            "passed": False,
        }

    async with AsyncSessionLocal() as session:
        run = await session.get(EvalRun, run_id)
        if run is None:  # pragma: no cover - row is created before we are scheduled
            return
        for key, value in fields.items():
            setattr(run, key, value)
        await session.commit()
    logger.info("eval_run_finished", run_id=str(run_id), status=fields["metrics"]["status"])


@router.post("/run", status_code=status.HTTP_202_ACCEPTED, response_model=EvalRunCreated)
async def run_eval(
    body: EvalRunRequest,
    request: Request,
    background: BackgroundTasks,
    admin: User = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> EvalRunCreated:
    """Start an eval run and return its id.

    The suites are LLM-graded over a dataset and take minutes, so they run in the
    background (and inside a worker thread — the runners are blocking, and calling
    them on the event loop would stall every other request in this worker). This
    is what makes the documented 202 honest: poll ``GET /eval/runs/{id}`` and read
    ``metrics.status`` (``running`` → ``completed``/``failed``).
    """
    dataset = body.dataset or _default_dataset()

    run = EvalRun(
        suite=body.suite,
        dataset=dataset,
        metrics={"status": STATUS_RUNNING},
        passed=False,
    )
    db.add(run)
    await db.flush()

    await write_audit(
        db,
        actor_id=admin.id,
        actor_roles=admin.role_names,
        action="eval.run",
        resource_type="eval",
        resource_id=str(run.id),
        outcome="success",
        ip=request.client.host if request.client else None,
        request_id=str(request.state.request_id),
        details={"suite": body.suite, "dataset": dataset, "status": STATUS_RUNNING},
    )
    await db.commit()

    background.add_task(_run_eval_in_background, run.id, body.suite, dataset)
    return EvalRunCreated(run_id=run.id)


@router.get("/runs", response_model=EvalRunListResponse)
async def list_runs(
    pg: Pagination = Depends(pagination_params),
    admin: User = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> EvalRunListResponse:
    total = (await db.execute(select(func.count()).select_from(EvalRun))).scalar_one()
    rows = (
        (
            await db.execute(
                select(EvalRun).order_by(EvalRun.created_at.desc()).offset(pg.offset).limit(pg.size)
            )
        )
        .scalars()
        .all()
    )
    return EvalRunListResponse(items=[EvalRunSummary.model_validate(r) for r in rows], total=total)


@router.get("/runs/{run_id}", response_model=EvalRunDetail)
async def get_run(
    run_id: uuid.UUID,
    admin: User = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> EvalRunDetail:
    run = await db.get(EvalRun, run_id)
    if run is None:
        raise NotFoundError("Eval run not found.")
    return EvalRunDetail(
        id=run.id,
        suite=run.suite,
        dataset=run.dataset,
        passed=run.passed,
        faithfulness_avg=float(run.faithfulness_avg) if run.faithfulness_avg is not None else None,
        hallucination_rate=float(run.hallucination_rate)
        if run.hallucination_rate is not None
        else None,
        created_at=run.created_at,
        run_label=run.run_label,
        answer_relevancy_avg=float(run.answer_relevancy_avg)
        if run.answer_relevancy_avg is not None
        else None,
        context_precision_avg=float(run.context_precision_avg)
        if run.context_precision_avg is not None
        else None,
        metrics=dict(run.metrics),
        commit_sha=run.commit_sha,
        faithfulness_threshold=get_settings().faithfulness_threshold,
    )
