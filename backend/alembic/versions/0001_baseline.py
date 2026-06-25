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
from app.db.base import Base
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DIALECT = postgresql.dialect()

# Append-only enforcement for the audit log (§6.15, §9: no UPDATE/DELETE).
# Each constant is a SINGLE statement (asyncpg's prepared protocol rejects
# multi-statement execs in online mode), so they are executed separately.
_AUDIT_FN_SQL = """
CREATE OR REPLACE FUNCTION aegis_forbid_audit_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only; % is not permitted', TG_OP;
END;
$$ LANGUAGE plpgsql
"""

_AUDIT_TRIGGER_SQL = """
CREATE TRIGGER trg_audit_log_append_only
    BEFORE UPDATE OR DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION aegis_forbid_audit_mutation()
"""

# Grant the least-privilege audit role INSERT/SELECT only (if it exists).
_AUDIT_GRANTS_SQL = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'aegis_audit') THEN
        GRANT INSERT, SELECT ON audit_log TO aegis_audit;
        GRANT USAGE, SELECT ON SEQUENCE audit_log_id_seq TO aegis_audit;
    END IF;
END
$$
"""


def upgrade() -> None:
    # gen_random_uuid() lives in pgcrypto.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # Create tables in FK-dependency order, then their standalone indexes.
    for table in Base.metadata.sorted_tables:
        op.execute(str(CreateTable(table).compile(dialect=_DIALECT)).strip())
        for index in table.indexes:
            op.execute(str(CreateIndex(index).compile(dialect=_DIALECT)).strip())

    # Make audit_log append-only at the database layer.
    op.execute(_AUDIT_FN_SQL)
    op.execute(_AUDIT_TRIGGER_SQL)
    op.execute(_AUDIT_GRANTS_SQL)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_log_append_only ON audit_log")
    op.execute("DROP FUNCTION IF EXISTS aegis_forbid_audit_mutation()")
    for table in reversed(Base.metadata.sorted_tables):
        op.execute(f'DROP TABLE IF EXISTS "{table.name}" CASCADE')
