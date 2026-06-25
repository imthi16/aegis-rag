"""Eval routes (CLAUDE.md §7 Eval). Role: admin only.

POST /eval/run        run RAGAS/DeepEval (local models) and persist an eval_runs row
GET  /eval/runs       list runs
GET  /eval/runs/{id}  run detail
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.logger import write_audit
from app.core.config import get_settings
from app.core.dependencies import get_db, require_roles
from app.core.exceptions import NotFoundError
from app.db.models.eval_run import EvalRun
from app.db.models.user import User
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

router = APIRouter(prefix="/eval", tags=["eval"])

_admin = require_roles(Role.ADMIN)


def _default_dataset() -> str:
    from app.eval import __file__ as eval_init

    return str(Path(eval_init).parent / "datasets" / "golden_qa.jsonl")


@router.post("/run", status_code=status.HTTP_202_ACCEPTED, response_model=EvalRunCreated)
async def run_eval(
    body: EvalRunRequest,
    request: Request,
    admin: User = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> EvalRunCreated:
    dataset = body.dataset or _default_dataset()
    metrics: dict[str, Any] = {}
    faithfulness: float | None = None
    answer_relevancy: float | None = None
    context_precision: float | None = None
    hallucination_rate: float | None = None

    if body.suite in ("ragas", "both"):
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

    if body.suite in ("deepeval", "both"):
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
    passed = gate_passed(faithfulness_val, hallucination_val)

    run = EvalRun(
        suite=body.suite,
        dataset=dataset,
        metrics=metrics,
        faithfulness_avg=round(faithfulness_val, 3),
        answer_relevancy_avg=round(answer_relevancy, 3) if answer_relevancy is not None else None,
        context_precision_avg=round(context_precision, 3)
        if context_precision is not None
        else None,
        hallucination_rate=round(hallucination_val, 3),
        passed=passed,
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
        details={"suite": body.suite, "passed": passed},
    )
    await db.commit()
    return EvalRunCreated(run_id=run.id)


@router.get("/runs", response_model=EvalRunListResponse)
async def list_runs(
    page: int = 1,
    size: int = 20,
    admin: User = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> EvalRunListResponse:
    total = (await db.execute(select(func.count()).select_from(EvalRun))).scalar_one()
    rows = (
        (
            await db.execute(
                select(EvalRun)
                .order_by(EvalRun.created_at.desc())
                .offset((page - 1) * size)
                .limit(size)
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
