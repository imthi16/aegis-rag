#!/usr/bin/env bash
# Aegis RAG — Postgres bootstrap, part 2: the least-privilege audit role.
#
# Runs once on first container start (docker-entrypoint-initdb.d). Unlike a .sql
# file, a .sh init script can read the environment, so the role's password comes
# from AUDIT_DB_PASSWORD instead of being a literal committed to the repo
# (CLAUDE.md §9: no secrets in code).
#
# The role is created LOGIN but powerless; migration 0001 grants it exactly
# INSERT + SELECT on audit_log (§8) and nothing else.
set -euo pipefail

if [[ -z "${AUDIT_DB_PASSWORD:-}" ]]; then
    echo "init: AUDIT_DB_PASSWORD is not set — refusing to create aegis_audit" >&2
    echo "init: set it in .env so the audit role does not get a default password" >&2
    exit 1
fi

if [[ "${AUDIT_DB_PASSWORD}" == CHANGE_ME* ]]; then
    echo "init: AUDIT_DB_PASSWORD still holds its CHANGE_ME placeholder" >&2
    echo "init: set a real secret before provisioning" >&2
    exit 1
fi

audit_user="${AUDIT_DB_USER:-aegis_audit}"

# The password is passed as a bound parameter (-v + quote_literal) rather than
# interpolated into the SQL text, so a quote or backslash in the secret cannot
# break out of the literal.
psql -v ON_ERROR_STOP=1 \
     --username "${POSTGRES_USER}" \
     --dbname "${POSTGRES_DB}" \
     -v audit_user="${audit_user}" \
     -v audit_password="${AUDIT_DB_PASSWORD}" <<'SQL'
SELECT format(
    'CREATE ROLE %I LOGIN PASSWORD %L',
    :'audit_user',
    :'audit_password'
) AS stmt
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'audit_user')
\gexec

-- Idempotent: keep the password in sync with the environment on re-provision.
SELECT format('ALTER ROLE %I PASSWORD %L', :'audit_user', :'audit_password') \gexec

-- The audit role must never accumulate broad rights.
SELECT format('REVOKE ALL ON SCHEMA public FROM %I', :'audit_user') \gexec
SELECT format('GRANT USAGE ON SCHEMA public TO %I', :'audit_user') \gexec
SQL

echo "init: created least-privilege audit role '${audit_user}'"
