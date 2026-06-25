"""Eval route integration (CLAUDE.md §7/§10 — Eval).

POST /eval/run persists an eval_runs row + eval.run audit; GET lists/details.
RAGAS/DeepEval runners are monkeypatched (no Ollama needed); the wiring uses
local models only in production.
"""

from __future__ import annotations

import app.api.v1.routes.eval as eval_routes
import pytest
from app.core.security import hash_password
from app.db.models import AuditLog, EvalRun, Role, User
from app.eval.deepeval_runner import DeepEvalResult
from app.eval.ragas_runner import RagasResult
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def _admin(db: AsyncSession, pw: str) -> None:
    role = Role(name="admin", description="admin")
    db.add(role)
    await db.flush()
    db.add(User(username="root", hashed_password=hash_password(pw), roles=[role]))
    await db.commit()


async def _token(client: AsyncClient, pw: str) -> str:
    resp = await client.post("/api/v1/auth/login", json={"username": "root", "password": pw})
    assert resp.status_code == 200
    return str(resp.json()["access_token"])


@pytest.mark.asyncio
async def test_run_eval_persists_and_audits(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    pw = "admin-pass-123"
    await _admin(db_session, pw)

    monkeypatch.setattr(
        eval_routes,
        "run_ragas",
        lambda dataset: RagasResult(
            faithfulness=0.9, answer_relevancy=0.8, context_precision=0.85, context_recall=0.8
        ),
    )
    monkeypatch.setattr(
        eval_routes,
        "run_deepeval",
        lambda dataset: DeepEvalResult(
            hallucination_rate=0.1, faithfulness=0.9, answer_relevancy=0.8
        ),
    )

    headers = {"Authorization": f"Bearer {await _token(client, pw)}"}
    run = await client.post("/api/v1/eval/run", json={"suite": "both"}, headers=headers)
    assert run.status_code == 202
    run_id = run.json()["run_id"]

    listing = await client.get("/api/v1/eval/runs", headers=headers)
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["passed"] is True

    detail = await client.get(f"/api/v1/eval/runs/{run_id}", headers=headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["passed"] is True
    assert "ragas" in body["metrics"] and "deepeval" in body["metrics"]
    assert body["faithfulness_threshold"] == 0.7

    # Persisted row + audit.
    assert (await db_session.execute(select(EvalRun))).scalars().all()
    audited = (
        (await db_session.execute(select(AuditLog).where(AuditLog.action == "eval.run")))
        .scalars()
        .all()
    )
    assert len(audited) == 1


@pytest.mark.asyncio
async def test_low_faithfulness_marks_run_failed(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    pw = "admin-pass-123"
    await _admin(db_session, pw)
    monkeypatch.setattr(
        eval_routes,
        "run_ragas",
        lambda dataset: RagasResult(
            faithfulness=0.3, answer_relevancy=0.5, context_precision=0.5, context_recall=0.5
        ),
    )
    headers = {"Authorization": f"Bearer {await _token(client, pw)}"}
    run = await client.post("/api/v1/eval/run", json={"suite": "ragas"}, headers=headers)
    assert run.status_code == 202
    detail = await client.get(f"/api/v1/eval/runs/{run.json()['run_id']}", headers=headers)
    assert detail.json()["passed"] is False
