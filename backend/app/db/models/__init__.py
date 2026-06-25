"""Model registry — importing this module registers all tables on Base.metadata.

Alembic's ``target_metadata`` and any ``create_all`` rely on every model being
imported here.
"""

from __future__ import annotations

from app.db.models.audit import AuditLog
from app.db.models.chunk import Chunk
from app.db.models.document import Document
from app.db.models.eval_run import EvalRun
from app.db.models.query_log import QueryLog
from app.db.models.role import Role, user_roles
from app.db.models.user import RefreshToken, User

__all__ = [
    "AuditLog",
    "Chunk",
    "Document",
    "EvalRun",
    "QueryLog",
    "RefreshToken",
    "Role",
    "User",
    "user_roles",
]
