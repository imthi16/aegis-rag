"""Eval DTOs (CLAUDE.md §7 Eval)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

EvalSuite = Literal["ragas", "deepeval", "both"]


class EvalRunRequest(BaseModel):
    dataset: str | None = None
    suite: EvalSuite = "both"


class EvalRunCreated(BaseModel):
    run_id: uuid.UUID


class EvalRunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    suite: str
    dataset: str
    passed: bool
    faithfulness_avg: float | None
    hallucination_rate: float | None
    created_at: datetime


class EvalRunListResponse(BaseModel):
    items: list[EvalRunSummary]
    total: int


class EvalRunDetail(EvalRunSummary):
    run_label: str | None
    answer_relevancy_avg: float | None
    context_precision_avg: float | None
    metrics: dict[str, Any]
    commit_sha: str | None
    faithfulness_threshold: float
