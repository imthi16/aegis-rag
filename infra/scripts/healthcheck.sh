#!/usr/bin/env bash
# Simple liveness/readiness probe for operators (CLAUDE.md §6.19).
# Usage: bash infra/scripts/healthcheck.sh [BASE_URL]
set -euo pipefail

BASE_URL="${1:-http://localhost:8000/api/v1}"

echo ">> Liveness:  ${BASE_URL}/health"
curl -fsS "${BASE_URL}/health" && echo

echo ">> Readiness: ${BASE_URL}/health/ready"
# /ready returns 503 until every dependency is up; show the body either way.
curl -s -o /tmp/aegis_ready.json -w "HTTP %{http_code}\n" "${BASE_URL}/health/ready" || true
cat /tmp/aegis_ready.json 2>/dev/null && echo
