"""baseline schema (CLAUDE.md §8)

Creates every table from the project metadata (parity with app/db/models), the
pgcrypto extension (for gen_random_uuid), and the append-only enforcement for
``audit_log`` (least-privilege grants to aegis_audit + a BEFORE UPDATE/DELETE
trigger that raises). Postgres-only by design.

Revision ID: 0001
Revises:
Create Date: 2026-06-25
"""

from __future__ import annotations

from collections.abc import Sequence

import app.db.models  # noqa: F401  (registers all tables on Base.metadata)
from alembic import op
from app.db.audit_ddl import (
    AUDIT_MUTATION_GUARD_FN,
    AUDIT_MUTATION_GUARD_TRIGGER,
    AUDIT_ROLE_GRANTS,
    DROP_AUDIT_MUTATION_GUARD_FN,
    DROP_AUDIT_MUTATION_GUARD_TRIGGER,
)
from app.db.base import Base
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DIALECT = postgresql.dialect()


def upgrade() -> None:
    # gen_random_uuid() lives in pgcrypto.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # Create tables in FK-dependency order, then their standalone indexes.
    for table in Base.metadata.sorted_tables:
        op.execute(str(CreateTable(table).compile(dialect=_DIALECT)).strip())
        for index in table.indexes:
            op.execute(str(CreateIndex(index).compile(dialect=_DIALECT)).strip())

    # Make audit_log append-only at the database layer.
    op.execute(AUDIT_MUTATION_GUARD_FN)
    op.execute(AUDIT_MUTATION_GUARD_TRIGGER)
    op.execute(AUDIT_ROLE_GRANTS)


def downgrade() -> None:
    op.execute(DROP_AUDIT_MUTATION_GUARD_TRIGGER)
    op.execute(DROP_AUDIT_MUTATION_GUARD_FN)
    for table in reversed(Base.metadata.sorted_tables):
        op.execute(f'DROP TABLE IF EXISTS "{table.name}" CASCADE')
