-- Aegis RAG — Postgres bootstrap, part 1 (CLAUDE.md §6.19, §8).
-- Runs once on first container start (docker-entrypoint-initdb.d/10-init.sql).
--
-- This file is intentionally secret-free: the least-privilege audit role is
-- created by the companion 20-audit-role.sh, which substitutes AUDIT_DB_PASSWORD
-- from the environment. A password literal here would be a committed credential
-- (§9: no secrets in the repo) and, worse, a known default on a LOGIN role.
--
-- The role stays powerless until `alembic upgrade head` runs: migration 0001
-- grants it INSERT, SELECT on audit_log (never UPDATE/DELETE), revokes mutation
-- from PUBLIC, and installs the BEFORE UPDATE/DELETE trigger that enforces
-- append-only at the database layer.

-- pgcrypto provides gen_random_uuid() for UUID primary keys (§8).
CREATE EXTENSION IF NOT EXISTS pgcrypto;
