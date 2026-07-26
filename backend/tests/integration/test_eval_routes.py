"""Eval route integration (CLAUDE.md §7/§10 — Eval).

POST /eval/run persists an eval_runs row + eval.run audit; GET lists/details.
RAGAS/DeepEval runners are monkeypatched (no Ollama needed); the wiring uses
local models only in production.

The suites run as a background task (they are blocking and LLM-graded, so running
them inline would stall the event loop and make the documented 202 a lie). The
worker opens its own session via ``AsyncSessionLocal`` because the request's
session is gone by then, so tests must rebind that to the test engine — otherwise
the completion write lands on the real DATABASE_URL and the row never updates
here. ``ASGITransport`` awaits background tasks before returning, so assertions
after the POST see the finished run.
"""

from __future__ import annotations

import threading

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
    client: AsyncClient,
    db_session: AsyncSession,
    app_sessions: None,
    monkeypatch: pytest.MonkeyPatch,
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
    # The run reports a terminal status so a poller can tell "done" from "running".
    assert body["metrics"]["status"] == eval_routes.STATUS_COMPLETED

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
    client: AsyncClient,
    db_session: AsyncSession,
    app_sessions: None,
    monkeypatch: pytest.MonkeyPatch,
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


@pytest.mark.asyncio
async def test_run_eval_returns_immediately_without_blocking(
    client: AsyncClient,
    db_session: AsyncSession,
    app_sessions: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The suites must not execute on the event loop inside the request handler.

    A runner that blocks its thread would stall every other request in the worker.
    Asserting it runs off-loop: the runner records the thread it executed on, and
    that must not be the loop's thread.
    """
    pw = "admin-pass-123"
    await _admin(db_session, pw)

    loop_thread = threading.current_thread().name
    ran_on: list[str] = []

    def _slow_ragas(dataset: str) -> RagasResult:
        ran_on.append(threading.current_thread().name)
        return RagasResult(
            faithfulness=0.9, answer_relevancy=0.8, context_precision=0.8, context_recall=0.8
        )

    monkeypatch.setattr(eval_routes, "run_ragas", _slow_ragas)

    headers = {"Authorization": f"Bearer {await _token(client, pw)}"}
    resp = await client.post("/api/v1/eval/run", json={"suite": "ragas"}, headers=headers)
    assert resp.status_code == 202
    assert resp.json()["run_id"]

    assert ran_on, "the suite never ran"
    assert (
        ran_on[0] != loop_thread
    ), f"suite ran on the event-loop thread ({loop_thread}); it must be offloaded"


@pytest.mark.asyncio
async def test_failed_run_is_recorded_not_left_running(
    client: AsyncClient,
    db_session: AsyncSession,
    app_sessions: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A crashing suite must land on `failed`, not sit at `running` forever."""
    pw = "admin-pass-123"
    await _admin(db_session, pw)

    def _boom(dataset: str) -> RagasResult:
        raise RuntimeError("ollama unreachable")

    monkeypatch.setattr(eval_routes, "run_ragas", _boom)

    headers = {"Authorization": f"Bearer {await _token(client, pw)}"}
    resp = await client.post("/api/v1/eval/run", json={"suite": "ragas"}, headers=headers)
    assert resp.status_code == 202  # accepting the job still succeeded

    detail = await client.get(f"/api/v1/eval/runs/{resp.json()['run_id']}", headers=headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["metrics"]["status"] == eval_routes.STATUS_FAILED
    assert body["metrics"]["error_type"] == "RuntimeError"
    assert body["passed"] is False


@pytest.mark.asyncio
async def test_eval_run_is_audited_before_the_work_starts(
    client: AsyncClient,
    db_session: AsyncSession,
    app_sessions: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The eval.run audit record is written when the job is accepted (§6.15)."""
    pw = "admin-pass-123"
    await _admin(db_session, pw)
    monkeypatch.setattr(
        eval_routes,
        "run_ragas",
        lambda dataset: RagasResult(
            faithfulness=0.9, answer_relevancy=0.9, context_precision=0.9, context_recall=0.9
        ),
    )
    headers = {"Authorization": f"Bearer {await _token(client, pw)}"}
    resp = await client.post("/api/v1/eval/run", json={"suite": "ragas"}, headers=headers)
    run_id = resp.json()["run_id"]

    audited = (
        (await db_session.execute(select(AuditLog).where(AuditLog.action == "eval.run")))
        .scalars()
        .all()
    )
    assert len(audited) == 1
    assert audited[0].resource_id == run_id
    assert audited[0].details["status"] == eval_routes.STATUS_RUNNING
