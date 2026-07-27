"""Raw DDL that enforces the append-only audit log (CLAUDE.md §6.15, §9).

Kept here rather than inline in the migration so the baseline migration and the
integration-test schema builder share one definition. Tests exercise the same
guard that production runs — a regression that weakens the trigger cannot pass
by virtue of the test schema never having had it.

Each constant is a SINGLE statement: asyncpg's prepared-statement protocol
rejects multi-statement execs, so callers execute them one at a time.
"""

from __future__ import annotations

AUDIT_MUTATION_GUARD_FN = """
CREATE OR REPLACE FUNCTION aegis_forbid_audit_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only; % is not permitted', TG_OP;
END;
$$ LANGUAGE plpgsql
"""

AUDIT_MUTATION_GUARD_TRIGGER = """
CREATE TRIGGER trg_audit_log_append_only
    BEFORE UPDATE OR DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION aegis_forbid_audit_mutation()
"""

DROP_AUDIT_MUTATION_GUARD_TRIGGER = "DROP TRIGGER IF EXISTS trg_audit_log_append_only ON audit_log"

DROP_AUDIT_MUTATION_GUARD_FN = "DROP FUNCTION IF EXISTS aegis_forbid_audit_mutation()"

# Least-privilege grants for the audit role (§8). Guarded by an existence check
# so the migration also applies to databases provisioned without init.sql.
AUDIT_ROLE_GRANTS = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'aegis_audit') THEN
        GRANT INSERT, SELECT ON audit_log TO aegis_audit;
        GRANT USAGE, SELECT ON SEQUENCE audit_log_id_seq TO aegis_audit;
        REVOKE UPDATE, DELETE ON audit_log FROM aegis_audit;
    END IF;
    REVOKE UPDATE, DELETE ON audit_log FROM PUBLIC;
END
$$
"""
