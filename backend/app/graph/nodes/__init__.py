"""Graph node helpers.

Per-request dependencies (db, user, request id) travel via the RunnableConfig
``configurable`` mapping rather than the graph state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain_core.runnables import RunnableConfig
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User


@dataclass
class NodeDeps:
    db: AsyncSession
    user: User
    request_id: str


def get_deps(config: RunnableConfig) -> NodeDeps:
    configurable: dict[str, Any] = dict(config.get("configurable") or {})
    return NodeDeps(
        db=configurable["db"],
        user=configurable["user"],
        request_id=str(configurable.get("request_id", "")),
    )
