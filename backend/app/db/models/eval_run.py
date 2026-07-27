"""Eval run model (CLAUDE.md §8).

Persists each RAGAS/DeepEval run's per-metric scores and pass/fail vs thresholds.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, DateTime, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Numeric

from app.db.base import Base


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    run_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    suite: Mapped[str] = mapped_column(Text, nullable=False)
    dataset: Mapped[str] = mapped_column(Text, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    faithfulness_avg: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    answer_relevancy_avg: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    context_precision_avg: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    hallucination_rate: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    commit_sha: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
