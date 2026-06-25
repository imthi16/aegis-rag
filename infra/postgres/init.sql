-- Aegis RAG — Postgres bootstrap (CLAUDE.md §6.19, §8).
-- Runs once on first container start (docker-entrypoint-initdb.d).
--
-- Step 1: enable required extensions and create the least-privilege audit role.
-- Step 2 (after `alembic upgrade head` creates audit_log) finalizes the grants:
--   GRANT INSERT, SELECT ON audit_log TO aegis_audit;  -- no UPDATE/DELETE
--   REVOKE UPDATE, DELETE ON audit_log FROM PUBLIC;
-- and (optionally) a BEFORE UPDATE/DELETE trigger that raises to enforce
-- append-only at the database layer.

-- pgcrypto provides gen_random_uuid() for UUID primary keys (§8).
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Least-privilege role used solely by the application's audit-write path.
-- Password is provided via the AUDIT_DB_PASSWORD env at provisioning time; the
-- placeholder below is replaced by the operator. The role is created LOGIN but
-- powerless until the Step-2 migration grants it INSERT/SELECT on audit_log.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'aegis_audit') THEN
    CREATE ROLE aegis_audit LOGIN PASSWORD 'CHANGE_ME_AUDIT_PASSWORD';
  END IF;
END
$$;

-- The audit role must never accumulate broad rights.
REVOKE ALL ON SCHEMA public FROM aegis_audit;
GRANT USAGE ON SCHEMA public TO aegis_audit;
