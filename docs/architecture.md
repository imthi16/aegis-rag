# Architecture

> Authoritative spec: [`../CLAUDE.md`](../CLAUDE.md). This document expands the
> design as modules land; Step 1 records the high-level shape.

## Components

- **FastAPI backend** — thin routers (§6.17) over services; app factory in
  `app/main.py`, single config ingress in `app/core/config.py`.
- **LangGraph pipeline** (§6.13–6.14) — `retrieve → rerank → grade_documents
  (CRAG) → [transform_query → retrieve] → generate → grade_faithfulness →
  finalize`. Routers terminate on `MAX_CORRECTION_ATTEMPTS` / `MAX_REGEN_ATTEMPTS`.
- **Retrieval** (§6.6–6.10) — FAISS dense + BM25 lexical fused with RRF, RBAC
  pre-filter applied **before** ranking, then cross-encoder rerank.
- **Generation** (§6.11–6.12) — Ollama (Qwen2.5 32B); grounded answers with
  mandatory `[n]` citations resolved to chunk offsets.
- **Audit** (§6.15) — hash-chained, HMAC-signed, append-only; verifier endpoint.
- **Datastore** — Postgres (system of record) + FAISS (live vectors).

## Request lifecycle (query)

1. Auth + role check (API), `request_id` bound to logs.
2. `allowed_document_ids(user)` → RBAC gate.
3. Hybrid retrieve (RBAC-filtered) → rerank → CRAG grade.
4. Generate → faithfulness grade → finalize with citations.
5. Write `query_log` row + `query.executed` audit record.

## Boundaries

- Zero egress at runtime; models pre-staged into volumes (Golden Rule 1).
- Offline-by-env enforced in `app/main.py` before any model import.
