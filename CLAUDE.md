# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Two documents in one.** Everything below the `— Aegis RAG` heading is the original **build specification** — the design contract (golden rules, module signatures, DB schema, API surface, per-module Definition of Done). The platform is now **built** and follows that spec closely; treat it as the authoritative source of intent when changing behavior. This top section is the **operational guide**: how to actually build, test, and reason about the code as it exists today.

## Working state

All 12 build steps are complete: backend (FastAPI + LangGraph), frontend (React/TS), infra (compose + airgap overlay), and eval harness are in place. Model weights for BGE-M3 and bge-reranker-v2-m3 are pre-staged under `./models/`.

**Known deviations from the spec below** (the spec text is not updated for these — trust the code):
- **Eval "DeepEval" suite is home-grown.** The third-party `deepeval` package is intentionally *not* a dependency (it ships telemetry + eager cloud-model imports that break zero-egress). `app/eval/deepeval_runner.py` is a built-in local evaluator driven by the local Ollama model. RAGAS is wired to local models via `app/eval/local_llm.py`. Nothing in eval may reach OpenAI.
- **`/query/stream` reveals a graded answer; it does not stream raw LLM tokens.** The graph runs to completion (including faithfulness grading) and the finished answer is then emitted as SSE frames, followed by `event: done` with the full `QueryResponse`. Streaming live tokens would put ungraded text in front of the user, and an answer later flagged `faithful=false` must never already have been rendered as trusted (Golden Rules 4 & 6). The frames reassemble into the answer byte-for-byte — see `tests/unit/test_sse.py`.
- **Uploaded originals are retained** under `DOCUMENT_STORAGE_PATH` (default `/data/documents`, inside the existing `aegis_data` volume) because `POST /documents/{id}/reindex` re-parses and re-embeds from them. `documents.source_path` therefore points at a file that exists; deleting a document unlinks it. A document whose original is missing fails reindex loudly (422) rather than half-reindexing.
- **The air-gap overlay needs `!override`, not just `!reset`.** Compose *merges* sequence keys across files, so a bare `networks: [aegis_internal]` in `docker-compose.airgap.yml` ADDS the internal network while leaving every service on the base file's routable `aegis_net` — containers keep a default gateway and full egress while the overlay still reads as correct. `!reset` only *clears* a key (correct for `ports`); replacing a value needs `!override`. `tests/integration/test_airgap_compose.py` resolves the real `docker compose config` and asserts each service is on `aegis_internal` **only**, so this cannot regress silently. It skips without the docker CLI (no daemon needed).
- **Audit immutability is enforced by the DB trigger, not by connecting as `aegis_audit`.** The app writes audit rows on its normal session so they commit atomically with the triggering operation (fail-closed). `audit_log` is protected for *every* role by the `BEFORE UPDATE OR DELETE` trigger in migration 0001; the least-privilege `aegis_audit` role (INSERT/SELECT only) is provisioned for out-of-band access. The DDL lives in `app/db/audit_ddl.py` so the migration and the integration-test schema share one definition.

## Commands

Backend dev runs inside `./backend`. The full local gate (mirrors CI in `.github/workflows/ci.yml`):
```bash
cd backend && ruff check . && ruff format --check . && mypy app && pytest
```
- **Single test:** `cd backend && pytest tests/unit/test_rrf.py` or `pytest tests/unit/test_rrf.py::test_name`
- **Integration tests need Postgres.** They *skip* unless a reachable asyncpg DSN is set: `TEST_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/aegis pytest tests/integration`. The fixture drops/recreates all tables per engine (plus the `audit_log` append-only trigger, so tests run against the production guard), so point it at a throwaway DB.
- **Lint/format/type auto-fix:** `make lint`, `make fmt` (writes), `make typecheck`, `make test` from repo root.
- **Eval gate:** `python eval/ci_gate.py --suite both` — a preflight (`app/eval/check_local_model`) checks the eval deps, the staged embedding weights, and that `OLLAMA_HOST` is reachable *and serving* `OLLAMA_MODEL`. Unavailable → exit 0 with a named reason (`--require` turns that into exit 2). **Once preflight passes, any evaluation error is a real failure (exit 2) and is never reported as a skip** — previously a blanket `except` made a broken suite indistinguishable from an unprovisioned runner.

Frontend (`./frontend`): `npm install && npm run typecheck && npm run build` (build is `tsc --noEmit && vite build`, so it is type-strict). `npm run dev` for the Vite dev server.

Stack lifecycle via Make (wraps `docker compose`): `make models` + `make pull-llm` (the only online steps) → `make build up migrate seed` → `make up-airgap` for the zero-egress overlay. `make logs` tails the backend.

## Architecture (the parts that span multiple files)

- **Config is the single env ingress.** Everything reads settings through `app/core/config.py` `get_settings()` (`@lru_cache`d) — never `os.environ` elsewhere. In `production` the `Settings` validator refuses to boot on missing/placeholder (`CHANGE_ME_*`) secrets and builds `DATABASE_URL` from parts.
- **RBAC is enforced at retrieval, not just the API.** The chain: `rbac/enforcement.allowed_document_ids(user)` → the set of permitted `faiss_id`s → passed into **both** `FaissStore.search` and `BM25Index.search` as `allowed_faiss_ids` *before* ranking → RRF fusion (`retrieval/rrf.py`) → `retrieval/hybrid.py` re-asserts visibility again when hydrating chunks from Postgres (defense in depth). An empty allowed set returns `[]`, which the graph turns into an "insufficient evidence" response. Any RBAC/visibility error fails **closed** (empty set).
- **The query pipeline is a compiled LangGraph state machine.** `graph/state.py` (a `TypedDict` threaded through nodes) + `graph/nodes/*.py` (each `(state) -> partial state`) + `graph/pipeline.py` `build_graph()` wires them with conditional routers. The corrective (CRAG) loop is `grade_documents → transform_query → retrieve` and the regen loop is `grade_faithfulness → generate`; both routers **must terminate** via `MAX_CORRECTION_ATTEMPTS`/`MAX_REGEN_ATTEMPTS`. Correction is *internal query rewrite + re-retrieval only* — never a web search. The `/query` route drives the compiled graph and writes one `query_log` row + one audit record per call.
- **ML models are process singletons loaded once at lifespan.** `get_embedder()`, `get_faiss_store()`, `get_reranker()`, `get_llm()` are `@lru_cache`d wrappers (`app/embeddings`, `app/retrieval`, `app/generation`). `app/main.py::_warm_singletons` calls each one during startup (in a worker thread — the loaders block) so no request pays the load cost and `/health/ready` reports real readiness: the `is_ready()` probes read `lru_cache` state, so without the warm-up they stay false until the first query. A component that fails to load is logged and leaves `ready=false` for itself rather than aborting boot. Offline env vars (`HF_HUB_OFFLINE` etc.) must be set before `FlagEmbedding`/`transformers` import.
- **Request guards live in `app/core/middleware.py`.** `RATE_LIMIT_PER_MINUTE` (slowapi, keyed on `X-Real-IP` which nginx always overwrites — uvicorn runs without `--proxy-headers`, so `request.client.host` would be nginx itself and every caller would share one bucket) and `REQUEST_MAX_BODY_MB`. Health probes are exempt from throttling. The 429 handler **must stay synchronous**: `SlowAPIMiddleware` dispatches via `sync_check_limits`, which silently swaps in slowapi's own handler for any coroutine, bypassing the §7 error envelope.
- **Audit is a fail-closed hash chain.** `audit/hash_chain.py` computes `HMAC-SHA256(canonical(payload) + prev_hash)`; `audit/logger.write_audit` appends and, if it fails, the triggering operation fails. The `audit_log` table is append-only, enforced by *both* a DB trigger and a least-privilege `aegis_audit` role (`INSERT, SELECT` only) created in `infra/postgres/init.sql`. `audit/verifier.verify_chain` recomputes every link and reports the first break.
- **Postgres is the system of record; FAISS is the live vector index.** Postgres holds the authoritative `faiss_id ↔ chunk` mapping. Ingestion (`ingestion/pipeline.py`) is transactional with FAISS/BM25 compensation: if the DB commit fails after a FAISS add, the vectors are removed so no orphans remain. `rank_bm25` is immutable, so BM25 is rebuilt on append.
- **Routers are thin.** `app/api/v1/routes/*` validate, enforce roles (`require_roles`), call into modules, write audit, return Pydantic DTOs (`app/schemas/*`). No business logic in routers.

## Non-negotiables (see Section 0 below for the full list)

Zero runtime egress; offline-by-env; RBAC at retrieval; no answer without citations; no CRAG web-search fallback; append-only audit; `temperature=0.0` for all grading/faithfulness LLM calls; strict typing (Pydantic v2 + mypy strict backend, strict TS frontend — no `Any`/`any` across module boundaries); fail closed on any auth/RBAC/audit error. Pin every dependency version.

---

# CLAUDE.md — Aegis RAG
> **You are the AI coding agent (Claude Code) building this repository.**
> This file is the single source of truth. Build the entire platform from it.
> Read Section 0 (Golden Rules) and Section 9 (Constraints) before writing any code, and re-read them before every architectural decision.
> When something is ambiguous, prefer the option that is (1) air-gapped, (2) auditable, (3) deterministic, in that order. Do not invent external dependencies.
---
## 0. Golden Rules (Non-Negotiable)
These override everything else, including convenience and "best-practice" defaults from libraries.
1. **ZERO EGRESS.** No code path may make a network call to any host outside the Docker network at runtime. No OpenAI, no Anthropic API, no HuggingFace Hub fetch, no telemetry, no `pip install` at runtime, no CDN. All model weights are pre-staged into volumes during a one-time online provisioning step, then the cluster runs offline.
2. **OFFLINE BY ENV.** Every process sets `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `HF_DATASETS_OFFLINE=1`. RAGAS and DeepEval MUST be wired to the local Ollama + local embeddings — their default is OpenAI and that is a hard violation.
3. **RBAC AT THE RETRIEVAL LAYER.** Access control is enforced where candidates are selected, not only at the API. A user must never receive — in an answer, a citation, a rerank candidate, or a log they can read — content from a document their roles do not permit.
4. **NO SILENT HALLUCINATION.** If retrieval/correction cannot ground an answer, the system returns an explicit "insufficient evidence" response. It never fabricates. In air-gapped mode the CRAG corrective action is NEVER web search — it is internal query rewrite + re-retrieval, or graceful refusal.
5. **EVERY SENSITIVE ACTION IS AUDITED.** Auth, query, document upload/delete, role change, and config change emit a tamper-evident audit record (hash-chained). Audit writes are append-only and must not be bypassable from application code.
6. **CITATIONS ARE MANDATORY.** Every factual claim in a generated answer maps to at least one retrieved chunk with `document_id`, `chunk_id`, and character offsets. An answer with claims but no citations is a bug.
7. **DETERMINISM WHERE IT MATTERS.** Set LLM `temperature=0.0` for grading/faithfulness nodes. Pin all dependency versions. Fix random seeds in eval.
8. **TYPED EVERYWHERE.** Pydantic v2 on the backend, strict TypeScript on the frontend. No `Any`, no `any`, no untyped dicts crossing a module boundary.
9. **FAIL CLOSED.** On any RBAC/auth/audit error, deny and log — never default-allow.
---
## 1. Project Overview
**Aegis RAG** is a fully air-gapped, zero-cloud **Sovereign RAG platform** for regulated industries (finance, government, healthcare). It lets authorized users ask natural-language questions over a private document corpus and receive **citation-backed, faithfulness-graded answers**, with **role-based access control enforced at retrieval** and **tamper-evident audit logging** mapped to HIPAA, GDPR, the EU AI Act, DORA, Swiss FADP/FINMA, and UAE PDPL/DIFC Reg 10.
**What makes it different from a generic RAG app:**
- **100% on-premise / air-gapped.** Inference (Qwen2.5 32B via Ollama), embeddings (BGE-M3), reranking (bge-reranker-v2-m3), and the vector index (FAISS) all run locally. Nothing leaves the perimeter.
- **LangGraph orchestration** with an explicit, inspectable state machine: hybrid retrieval (FAISS dense + BM25 lexical fused with RRF) → cross-encoder reranking → **CRAG self-correction** (document-relevance grading + corrective re-retrieval) → grounded generation → **faithfulness grading** → citation finalization.
- **RBAC at the retrieval layer.** Documents carry a classification and an allowed-roles set; the candidate set is filtered by the caller's roles before ranking.
- **Span-level source tracing.** Answers carry chunk-level citations with character offsets into the source document; an optional sentence-attribution pass tightens claims to spans.
- **Tamper-evident audit log.** Hash-chained, HMAC-signed, append-only, with an integrity-verification endpoint and compliance field mapping.
- **CI-gated evaluation.** RAGAS + DeepEval faithfulness / hallucination / answer-relevancy / context-precision metrics run in CI and fail the build below thresholds — all using local models only.
**Primary users / roles (default):** `admin`, `compliance_auditor`, `analyst`, `viewer`. Document classifications (default): `public`, `internal`, `confidential`, `restricted`.
**Target regulatory frameworks:** HIPAA (§164.312(b) audit controls), GDPR, EU AI Act (Art. 12 record-keeping, Art. 13 transparency), DORA (ICT risk + logging), Swiss FADP / FINMA, UAE PDPL / DIFC Reg 10. See Section 11 for the field-level mapping.
---
## 2. Full Tech Stack
Pin every version. Do not upgrade across majors without an explicit instruction.
**Backend (Python 3.11)**
- FastAPI (ASGI, served by Uvicorn behind Gunicorn workers in prod)
- Pydantic v2 + pydantic-settings (config)
- LangGraph (orchestration state machine) + LangChain core (only the offline-safe primitives)
- SQLAlchemy 2.x (async) + asyncpg (driver) + Alembic (migrations)
- FAISS (`faiss-cpu`, or `faiss-gpu` if CUDA is provisioned) — dense vector index
- `rank_bm25` (BM25Okapi) — lexical channel
- FlagEmbedding — BGE-M3 embeddings (`BGEM3FlagModel`) and `bge-reranker-v2-m3` (`FlagReranker`)
- Ollama Python client (`ollama`) — talks to the Ollama server hosting `qwen2.5:32b`
- PyMuPDF (`fitz`), `python-docx`, `beautifulsoup4` — document parsing (no network-dependent parsers)
- `python-jose[cryptography]` or `PyJWT` — JWT; `passlib[argon2]` / `argon2-cffi` — password hashing
- `structlog` — structured JSON logging; OpenTelemetry SDK (export to a **local** collector only, optional)
- `slowapi` — rate limiting
**Inference / Models**
- LLM: **Qwen2.5 32B** via Ollama (`qwen2.5:32b`). ~20 GB at Q4; needs a 24 GB+ GPU or a large-RAM CPU box. Treated as a network service inside the compose network.
- Embeddings: **BGE-M3** (dense, 1024-dim, normalized). Weights pre-staged at `EMBEDDING_MODEL_PATH`.
- Reranker: **bge-reranker-v2-m3** cross-encoder. Weights pre-staged at `RERANKER_MODEL_PATH`.
**Datastore**
- PostgreSQL 16 (system of record: users/roles, document + chunk metadata, query log, audit log, eval runs). FAISS holds vectors; Postgres holds everything authoritative including the FAISS-id ↔ chunk mapping.
**Frontend**
- React 18 + TypeScript (strict) + Vite
- TailwindCSS + shadcn/ui (Radix primitives)
- TanStack Query (server state) + Zustand (client/auth state)
- React Router
**Evaluation**
- RAGAS (faithfulness, answer_relevancy, context_precision, context_recall) — **wired to local Ollama + local embeddings**
- DeepEval (hallucination, faithfulness, answer-relevancy) — **wired to a local LLM**
**Infra**
- Docker + docker-compose (with an `airgap` overlay)
- Nginx (reverse proxy + static frontend)
- GitHub Actions (CI: lint, type-check, unit/integration tests, eval gate)
---
## 3. Exact Folder Structure to Create
Create this tree exactly. Empty `__init__.py` files where needed. Do not flatten or rename.
```
aegis-rag/
├── CLAUDE.md
├── README.md
├── .env.example
├── .gitignore
├── docker-compose.yml
├── docker-compose.airgap.yml
├── Makefile
│
├── backend/
│   ├── pyproject.toml
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── alembic.ini
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                      # FastAPI app factory, router mount, middleware, lifespan
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py                # Settings (pydantic-settings), single source for env
│   │   │   ├── logging.py               # structlog config (JSON), request-id binding
│   │   │   ├── security.py              # password hashing, JWT encode/decode
│   │   │   ├── dependencies.py          # get_current_user, require_roles, get_db
│   │   │   └── exceptions.py            # AppError hierarchy + handlers
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                  # DeclarativeBase, naming convention
│   │   │   ├── session.py               # async engine + session factory
│   │   │   └── models/
│   │   │       ├── __init__.py
│   │   │       ├── user.py
│   │   │       ├── role.py              # Role, user_roles assoc, permission (optional)
│   │   │       ├── document.py
│   │   │       ├── chunk.py
│   │   │       ├── audit.py
│   │   │       ├── query_log.py
│   │   │       └── eval_run.py
│   │   ├── schemas/                     # Pydantic request/response DTOs
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── document.py
│   │   │   ├── query.py
│   │   │   ├── audit.py
│   │   │   └── eval.py
│   │   ├── rbac/
│   │   │   ├── __init__.py
│   │   │   ├── classifications.py       # enums: Role, Classification + ordering
│   │   │   └── enforcement.py           # allowed_doc_ids(user), filter_candidates(...)
│   │   ├── ingestion/
│   │   │   ├── __init__.py
│   │   │   ├── parsers.py               # pdf/docx/txt/html -> normalized text + page map
│   │   │   ├── chunker.py               # token-aware recursive chunking + offsets
│   │   │   └── pipeline.py              # orchestrates parse->chunk->embed->index->persist
│   │   ├── embeddings/
│   │   │   ├── __init__.py
│   │   │   └── embedder.py              # BGE-M3 singleton, encode(texts) -> np.ndarray
│   │   ├── retrieval/
│   │   │   ├── __init__.py
│   │   │   ├── faiss_store.py           # build/load/save/search FAISS, id mapping
│   │   │   ├── bm25_index.py            # build/load/save BM25, search
│   │   │   ├── rrf.py                   # reciprocal rank fusion
│   │   │   ├── hybrid.py                # dense + lexical + RRF + RBAC pre-filter
│   │   │   └── reranker.py              # bge-reranker-v2-m3 singleton, rerank(query, cands)
│   │   ├── generation/
│   │   │   ├── __init__.py
│   │   │   ├── llm.py                   # Ollama client wrapper (chat, temperature, num_ctx)
│   │   │   ├── prompts.py               # all prompt templates (generation/grading)
│   │   │   └── citations.py             # build citations + optional sentence attribution
│   │   ├── graph/
│   │   │   ├── __init__.py
│   │   │   ├── state.py                 # GraphState (TypedDict/Pydantic)
│   │   │   ├── pipeline.py              # build_graph() -> compiled StateGraph
│   │   │   └── nodes/
│   │   │       ├── __init__.py
│   │   │       ├── retrieve.py
│   │   │       ├── rerank.py
│   │   │       ├── grade_documents.py   # CRAG relevance grading
│   │   │       ├── transform_query.py   # corrective query rewrite
│   │   │       ├── generate.py
│   │   │       ├── grade_faithfulness.py
│   │   │       └── finalize.py          # attach citations, build response
│   │   ├── audit/
│   │   │   ├── __init__.py
│   │   │   ├── hash_chain.py            # canonical serialization + hash linking + HMAC
│   │   │   ├── logger.py                # async append, fail-closed
│   │   │   └── verifier.py              # full-chain integrity check
│   │   ├── eval/
│   │   │   ├── __init__.py
│   │   │   ├── local_llm.py             # langchain ChatOllama / wrappers for RAGAS+DeepEval
│   │   │   ├── ragas_runner.py
│   │   │   ├── deepeval_runner.py
│   │   │   └── datasets/
│   │   │       └── golden_qa.jsonl      # seed eval set (question, ground_truth, contexts)
│   │   └── api/
│   │       ├── __init__.py
│   │       └── v1/
│   │           ├── __init__.py
│   │           ├── router.py            # aggregates all routers under /api/v1
│   │           └── routes/
│   │               ├── __init__.py
│   │               ├── auth.py
│   │               ├── documents.py
│   │               ├── query.py
│   │               ├── audit.py
│   │               ├── eval.py
│   │               ├── admin.py
│   │               └── health.py
│   ├── alembic/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py
│       ├── unit/
│       │   ├── test_rrf.py
│       │   ├── test_chunker.py
│       │   ├── test_hash_chain.py
│       │   └── test_rbac.py
│       └── integration/
│           ├── test_auth_flow.py
│           ├── test_ingestion.py
│           ├── test_query_pipeline.py
│           └── test_audit_verify.py
│
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── index.html
│   ├── Dockerfile
│   ├── nginx.conf
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── index.css
│       ├── api/
│       │   ├── client.ts                # fetch wrapper, auth header, 401 refresh
│       │   ├── auth.ts
│       │   ├── query.ts
│       │   ├── documents.ts
│       │   ├── audit.ts
│       │   └── eval.ts
│       ├── store/
│       │   └── authStore.ts             # Zustand: tokens, user, roles
│       ├── hooks/
│       │   ├── useQueryStream.ts
│       │   └── useAuth.ts
│       ├── types/
│       │   └── api.ts                    # mirrors backend Pydantic DTOs
│       ├── components/
│       │   ├── ui/                       # shadcn components
│       │   ├── chat/
│       │   │   ├── ChatPanel.tsx
│       │   │   ├── MessageBubble.tsx
│       │   │   └── EvidencePanel.tsx     # shows grades + faithfulness + retrieved chunks
│       │   ├── citations/
│       │   │   └── CitationChip.tsx
│       │   ├── documents/
│       │   │   ├── DocumentList.tsx
│       │   │   └── UploadDialog.tsx
│       │   ├── audit/
│       │   │   └── AuditTable.tsx
│       │   └── auth/
│       │       └── LoginForm.tsx
│       ├── pages/
│       │   ├── LoginPage.tsx
│       │   ├── ChatPage.tsx
│       │   ├── DocumentsPage.tsx
│       │   ├── AuditPage.tsx
│       │   └── EvalPage.tsx
│       └── lib/
│           └── utils.ts
│
├── infra/
│   ├── nginx/
│   │   └── nginx.conf                    # reverse proxy api + serve static
│   ├── postgres/
│   │   └── init.sql                      # extensions, restricted audit role/grants
│   ├── prometheus/                       # optional, local only
│   │   └── prometheus.yml
│   └── scripts/
│       ├── download_models.sh            # ONLINE step: pull BGE-M3 + reranker weights
│       ├── pull_ollama_model.sh          # ONLINE step: ollama pull qwen2.5:32b
│       ├── seed_admin.py                 # create first admin + default roles
│       └── healthcheck.sh
│
├── eval/
│   ├── ci_gate.py                        # runs RAGAS+DeepEval, exits nonzero below thresholds
│   └── datasets/
│       └── golden_qa.jsonl
│
├── docs/
│   ├── architecture.md
│   ├── compliance-mapping.md
│   ├── threat-model.md
│   └── runbook-airgap-provisioning.md
│
└── .github/
    └── workflows/
        └── ci.yml
```
---
## 4. All Environment Variables
Create `.env.example` with exactly these keys and placeholder values. The backend reads them only through `app/core/config.py`. Never read `os.environ` directly elsewhere.
```dotenv
# ── App ─────────────────────────────────────────────
APP_ENV=production                       # production | development | test
APP_HOST=0.0.0.0
APP_PORT=8000
APP_NAME=aegis-rag
LOG_LEVEL=INFO                           # DEBUG | INFO | WARNING | ERROR
LOG_FORMAT=json                          # json | console
CORS_ORIGINS=http://localhost:5173,http://localhost:8080
RATE_LIMIT_PER_MINUTE=60
REQUEST_MAX_BODY_MB=50
# ── Postgres ────────────────────────────────────────
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=aegis
POSTGRES_USER=aegis_app
POSTGRES_PASSWORD=CHANGE_ME_STRONG_PASSWORD
# Built by config if unset:
DATABASE_URL=postgresql+asyncpg://aegis_app:CHANGE_ME_STRONG_PASSWORD@postgres:5432/aegis
# Separate, write-only role for audit appends (least privilege):
AUDIT_DB_USER=aegis_audit
AUDIT_DB_PASSWORD=CHANGE_ME_AUDIT_PASSWORD
# ── Ollama (LLM) ────────────────────────────────────
OLLAMA_HOST=http://ollama:11434
OLLAMA_MODEL=qwen2.5:32b
OLLAMA_NUM_CTX=8192
OLLAMA_TEMPERATURE_GEN=0.1
OLLAMA_TEMPERATURE_GRADE=0.0
OLLAMA_REQUEST_TIMEOUT_S=180
OLLAMA_KEEP_ALIVE=30m
# ── Embeddings (BGE-M3) ─────────────────────────────
EMBEDDING_MODEL_PATH=/models/bge-m3
EMBEDDING_DIM=1024
EMBEDDING_DEVICE=cpu                     # cpu | cuda
EMBEDDING_BATCH_SIZE=16
EMBEDDING_MAX_LENGTH=8192
EMBEDDING_NORMALIZE=true
# ── Reranker (bge-reranker-v2-m3) ───────────────────
RERANKER_MODEL_PATH=/models/bge-reranker-v2-m3
RERANKER_DEVICE=cpu                      # cpu | cuda
RERANKER_USE_FP16=true
RERANKER_BATCH_SIZE=16
# ── Retrieval / Fusion / CRAG ───────────────────────
FAISS_INDEX_PATH=/data/faiss/index.faiss
FAISS_INDEX_TYPE=flat_ip                 # flat_ip | hnsw
FAISS_HNSW_M=32
FAISS_HNSW_EF_SEARCH=128
BM25_INDEX_PATH=/data/bm25/bm25.pkl
RETRIEVAL_TOP_K=40                       # per channel before fusion
RRF_K=60
RERANK_TOP_N=8                           # passed to generation
OVERFETCH_FACTOR=3                       # multiply top_k when RBAC post-filtering
CRAG_RELEVANCE_THRESHOLD=0.5             # mean relevance below -> corrective path
CRAG_MIN_RELEVANT_DOCS=2
FAITHFULNESS_THRESHOLD=0.7
MAX_CORRECTION_ATTEMPTS=1                # internal re-retrieval rounds (NO web search)
MAX_REGEN_ATTEMPTS=1
# ── Chunking ────────────────────────────────────────
CHUNK_SIZE_TOKENS=512
CHUNK_OVERLAP_TOKENS=64
ALLOWED_FILE_TYPES=pdf,docx,txt,md,html
UPLOAD_MAX_SIZE_MB=50
# ── Auth (JWT) ──────────────────────────────────────
JWT_SECRET_KEY=CHANGE_ME_64_CHAR_RANDOM_HEX
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
PASSWORD_HASH_SCHEME=argon2
# ── Audit (tamper-evident) ──────────────────────────
AUDIT_HMAC_KEY=CHANGE_ME_64_CHAR_RANDOM_HEX
AUDIT_CHAIN_GENESIS_HASH=0000000000000000000000000000000000000000000000000000000000000000
# ── Offline enforcement (DO NOT CHANGE) ─────────────
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1
HF_DATASETS_OFFLINE=1
# ── Frontend (Vite, build-time) ─────────────────────
VITE_API_BASE_URL=/api/v1
```
Rules:
- `config.py` must **fail to start** if any of these is missing/blank in `production`: `JWT_SECRET_KEY`, `AUDIT_HMAC_KEY`, `POSTGRES_PASSWORD`, and they must not equal their `CHANGE_ME_*` placeholders.
- `config.py` builds `DATABASE_URL` from parts when not explicitly provided.
---
## 5. Implementation Order (Step by Step)
Build in this order. Do not start a step until the previous step's Definition of Done (Section 10) passes. Commit at every step boundary.
1. **Scaffold + config.** Create the tree, `pyproject.toml`/`requirements.txt`, `config.py`, `logging.py`, `exceptions.py`, `main.py` app factory with `/health`. `docker-compose.yml` with postgres + backend + ollama + frontend stubs. `infra/scripts/download_models.sh` and `pull_ollama_model.sh`.
2. **Database + models + migrations.** `db/base.py`, `db/session.py`, all SQLAlchemy models (Section 8), Alembic baseline migration, `init.sql` (extensions + restricted audit role). `seed_admin.py`.
3. **Auth + RBAC core.** `security.py`, `dependencies.py` (`get_current_user`, `require_roles`), `rbac/classifications.py`, `rbac/enforcement.py`, auth routes. Tests for login/refresh and role gating.
4. **Audit subsystem.** `audit/hash_chain.py`, `audit/logger.py`, `audit/verifier.py`, audit routes (`/audit`, `/audit/verify`). Wire auth events to audit. Tests for chain integrity + tamper detection. **Do this before query/ingestion so everything downstream is audited from birth.**
5. **Embeddings + FAISS + BM25.** `embeddings/embedder.py` (singleton), `retrieval/faiss_store.py`, `retrieval/bm25_index.py`. Tests with tiny fixtures.
6. **Ingestion pipeline.** `ingestion/parsers.py`, `ingestion/chunker.py`, `ingestion/pipeline.py`; document routes (upload/list/get/delete/reindex). Persist chunks + FAISS ids + BM25 rebuild. RBAC applied to list/get.
7. **Hybrid retrieval + reranker.** `retrieval/rrf.py`, `retrieval/hybrid.py` (with RBAC pre-filter), `retrieval/reranker.py`. Tests for RRF correctness and RBAC isolation.
8. **Generation + prompts + citations.** `generation/llm.py`, `generation/prompts.py`, `generation/citations.py`.
9. **LangGraph pipeline.** `graph/state.py`, all `graph/nodes/*`, `graph/pipeline.py`. Query route (`/query`, `/query/stream`) drives the compiled graph. Every query writes a `query_log` row and an audit record.
10. **Eval harness.** `eval/local_llm.py`, `eval/ragas_runner.py`, `eval/deepeval_runner.py`, `eval/ci_gate.py`, seed `golden_qa.jsonl`, eval routes. Wire `ci_gate.py` into `.github/workflows/ci.yml`.
11. **Frontend.** API client + auth store, then Login → Chat (with EvidencePanel + citations) → Documents → Audit → Eval pages.
12. **Infra hardening.** Nginx reverse proxy, `docker-compose.airgap.yml` overlay (no published ports except nginx, no external DNS), healthchecks, README + runbook.
---
## 6. Each Module — Path, What to Build, Key Functions, Business Rules
> Signatures below are the contract. Implement them exactly (names/shapes). Add private helpers as needed. Critical/ambiguous logic includes reference code; everything else is specified by signature + rules.
### 6.1 `app/core/config.py`
**Build:** A `Settings(BaseSettings)` class (pydantic-settings) exposing every env var in Section 4 with types and defaults; a cached `get_settings()`.
**Key functions:**
```python
class Settings(BaseSettings):
    app_env: Literal["production","development","test"]
    database_url: str | None = None
    # ... all keys, typed ...
    @model_validator(mode="after")
    def _build_and_validate(self) -> "Settings": ...   # build DATABASE_URL; reject placeholders in prod
@lru_cache
def get_settings() -> Settings: ...
```
**Rules:** Single ingress for env. In `production`, raise on missing/placeholder secrets. `CORS_ORIGINS` parses comma-separated → list.
### 6.2 `app/db/` (base, session, models)
**Build:** Async engine + `async_sessionmaker`; `DeclarativeBase` with a naming convention for deterministic constraint names; all models per Section 8.
**Key functions:** `get_engine()`, `AsyncSessionLocal`, FastAPI dep `get_db() -> AsyncIterator[AsyncSession]`.
**Rules:** UUID PKs for domain tables; `audit_log` uses `BIGSERIAL` (monotonic ordering). `created_at`/`updated_at` server defaults. No business logic in models.
### 6.3 `app/core/security.py` + `app/core/dependencies.py` + `app/rbac/`
**Build:** Password hashing (argon2), JWT encode/decode, current-user + role dependencies, RBAC enforcement.
**Key functions:**
```python
# security.py
def hash_password(raw: str) -> str: ...
def verify_password(raw: str, hashed: str) -> bool: ...
def create_access_token(sub: str, roles: list[str]) -> str: ...
def create_refresh_token(sub: str) -> str: ...
def decode_token(token: str) -> TokenPayload: ...   # raises on expiry/invalid
# dependencies.py
async def get_current_user(token=Depends(oauth2), db=Depends(get_db)) -> User: ...
def require_roles(*allowed: Role) -> Callable: ...   # FastAPI dependency factory
# rbac/classifications.py
class Role(str, Enum): ADMIN="admin"; COMPLIANCE_AUDITOR="compliance_auditor"; ANALYST="analyst"; VIEWER="viewer"
class Classification(str, Enum): PUBLIC="public"; INTERNAL="internal"; CONFIDENTIAL="confidential"; RESTRICTED="restricted"
# rbac/enforcement.py
async def allowed_document_ids(db, user: User) -> set[UUID]: ...
def is_document_visible(doc, user_roles: set[Role]) -> bool: ...
def filter_chunk_candidates(candidates: list[Candidate], allowed_doc_ids: set[UUID]) -> list[Candidate]: ...
```
**Business rules:**
- A document is visible to a user iff the user has at least one role in `document.allowed_roles` OR the user is `admin`. `admin` sees everything; `compliance_auditor` can read audit + metadata but follows the same content visibility rules unless explicitly granted.
- `allowed_document_ids` is the authoritative gate used by retrieval. Compute it from Postgres per request (cache per-request only, never cross-request).
- Fail closed: any error computing visibility → empty allowed set.
### 6.4 `app/ingestion/`
**Build:** Parsers, token-aware chunker, and the end-to-end pipeline.
**Key functions:**
```python
# parsers.py
@dataclass
class ParsedDoc: text: str; pages: list[PageSpan]; content_hash: str; meta: dict
def parse_document(path: str, filetype: str) -> ParsedDoc: ...   # pdf=PyMuPDF, docx=python-docx, html=bs4, txt/md=plain
# chunker.py
@dataclass
class Chunk: index: int; content: str; token_count: int; char_start: int; char_end: int; page_number: int | None
def chunk_text(parsed: ParsedDoc, size_tokens: int, overlap_tokens: int) -> list[Chunk]: ...
# pipeline.py
async def ingest_document(db, *, file_path: str, filename: str, filetype: str,
                          classification: Classification, allowed_roles: list[Role],
                          uploaded_by: UUID) -> Document: ...
```
**Business rules:**
- Token counting uses the **local** BGE-M3 tokenizer loaded offline from `EMBEDDING_MODEL_PATH` (never tiktoken/network). Recursive splitting on paragraph→sentence boundaries; preserve `char_start`/`char_end` into the normalized source text for span tracing.
- `content_hash = sha256(normalized_text)`. If a document with the same hash + same classification exists, skip re-embedding (dedupe) and return existing.
- Pipeline order: parse → chunk → embed (batch) → add to FAISS (capture `faiss_id`) → persist `Document` + `Chunk` rows in a single transaction → rebuild/append BM25 → emit audit record `document.ingested`. If FAISS add succeeds but DB commit fails, roll back FAISS additions (compensating delete) — never leave orphan vectors.
- Reject files whose type ∉ `ALLOWED_FILE_TYPES` or size > `UPLOAD_MAX_SIZE_MB`.
### 6.5 `app/embeddings/embedder.py`
**Build:** A process-singleton wrapper over `BGEM3FlagModel`.
**Key functions:**
```python
class Embedder:
    def __init__(self, model_path: str, device: str, max_length: int, normalize: bool): ...
    def encode(self, texts: list[str], batch_size: int) -> np.ndarray:  # (n, 1024) float32, L2-normalized
        ...
    def encode_query(self, text: str) -> np.ndarray: ...
@lru_cache
def get_embedder() -> Embedder: ...
```
**Rules:** Load once at startup (lifespan), reuse. Always return float32, L2-normalized (so FAISS inner product = cosine). Set offline env before import. Embedding for a query and for documents must use the same model + normalization.
### 6.6 `app/retrieval/faiss_store.py`
**Build:** Build/load/save/search over an ID-mapped FAISS index.
**Key functions:**
```python
class FaissStore:
    def __init__(self, index_path: str, dim: int, index_type: str): ...
    def load_or_create(self) -> None: ...
    def add(self, vectors: np.ndarray, ids: list[int]) -> None: ...        # IndexIDMap2
    def remove(self, ids: list[int]) -> None: ...
    def search(self, query: np.ndarray, top_k: int,
               allowed_faiss_ids: set[int] | None = None) -> list[tuple[int, float]]: ...
    def save(self) -> None: ...
@lru_cache
def get_faiss_store() -> FaissStore: ...
```
**Rules:**
- Use `IndexFlatIP` wrapped in `IndexIDMap2` for `flat_ip`; `IndexHNSWFlat` for `hnsw`. `faiss_id` is a stable 63-bit int generated at chunk-insert time and stored in Postgres.
- **RBAC pre-filter:** when `allowed_faiss_ids` is provided, prefer a FAISS `IDSelectorBatch` if the index type supports it; otherwise over-fetch `top_k * OVERFETCH_FACTOR` then drop ids ∉ allowed set and truncate to `top_k`. Document which path is taken. Robustness > cleverness.
- Persist after every batch of adds/removes; load on startup.
### 6.7 `app/retrieval/bm25_index.py`
**Build:** A persisted BM25Okapi over the tokenized chunk corpus.
**Key functions:**
```python
class BM25Index:
    def build(self, corpus: list[tuple[int, str]]) -> None: ...   # (faiss_id, content)
    def add(self, items: list[tuple[int, str]]) -> None: ...       # rebuild on append (rank_bm25 is immutable)
    def search(self, query: str, top_k: int,
               allowed_faiss_ids: set[int] | None = None) -> list[tuple[int, float]]: ...
    def save(self) -> None: ...
    def load(self) -> None: ...
```
**Rules:** Tokenize with a simple, deterministic, offline tokenizer (lowercase + unicode word split). Maintain the `row_index → faiss_id` mapping alongside the model. Apply the same `allowed_faiss_ids` RBAC filter as FAISS. Persist via pickle to `BM25_INDEX_PATH`.
### 6.8 `app/retrieval/rrf.py`
**Build:** Reciprocal Rank Fusion. This must be exact:
```python
def reciprocal_rank_fusion(
    ranked_lists: list[list[int]],   # each is faiss_ids ordered best->worst
    k: int = 60,
) -> list[tuple[int, float]]:
    scores: dict[int, float] = {}
    for ranked in ranked_lists:
        for rank, doc_id in enumerate(ranked):           # rank starts at 0
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
```
**Rules:** Pure, deterministic, unit-tested. No scoring normalization across channels — RRF uses ranks only, which is why it is robust to incomparable score scales (BM25 vs cosine).
### 6.9 `app/retrieval/hybrid.py`
**Build:** The full hybrid retrieval entrypoint used by the graph.
**Key functions:**
```python
@dataclass
class Candidate: faiss_id: int; chunk_id: UUID; document_id: UUID; content: str
    char_start: int; char_end: int; page_number: int | None; score: float
async def hybrid_retrieve(db, *, query: str, user: User, top_k: int) -> list[Candidate]: ...
```
**Business rules (order matters):**
1. Compute `allowed_faiss_ids` from `allowed_document_ids(user)` (RBAC) — **before** searching.
2. Dense search (FAISS) and lexical search (BM25) each return up to `top_k` ids, both already RBAC-filtered.
3. Fuse with `reciprocal_rank_fusion([dense_ids, bm25_ids], k=RRF_K)`.
4. Hydrate fused ids → `Candidate` from Postgres `chunks` (this also re-asserts RBAC: any chunk whose document is not visible is dropped — defense in depth).
5. Return top `top_k` candidates. If allowed set is empty, return `[]` (the graph then returns "insufficient evidence / no accessible documents").
### 6.10 `app/retrieval/reranker.py`
**Build:** Cross-encoder reranking singleton.
**Key functions:**
```python
class Reranker:
    def __init__(self, model_path: str, device: str, use_fp16: bool): ...
    def rerank(self, query: str, candidates: list[Candidate], top_n: int) -> list[Candidate]: ...
@lru_cache
def get_reranker() -> Reranker: ...
```
**Rules:** Score each `(query, candidate.content)` pair with `FlagReranker`; sort desc; attach the rerank score to `Candidate.score`; return top `top_n` (= `RERANK_TOP_N`). Batch for throughput. Loaded once at startup.
### 6.11 `app/generation/llm.py` + `prompts.py`
**Build:** Ollama wrapper + all prompt templates.
**Key functions:**
```python
# llm.py
class LLM:
    async def chat(self, messages: list[dict], *, temperature: float, num_ctx: int,
                   format: Literal["", "json"] = "") -> str: ...
@lru_cache
def get_llm() -> LLM: ...
# prompts.py  (constants returning formatted strings)
def generation_prompt(query: str, contexts: list[Candidate]) -> list[dict]: ...
def doc_relevance_prompt(query: str, context: str) -> list[dict]: ...      # -> JSON {"relevant": bool, "score": float}
def query_rewrite_prompt(query: str, reason: str) -> list[dict]: ...
def faithfulness_prompt(answer: str, contexts: list[Candidate]) -> list[dict]: ...  # -> JSON verdict + unsupported claims
```
**Rules:** Generation prompt must instruct the model to (a) answer **only** from the provided numbered contexts, (b) cite sources inline as `[n]` referencing the context index, (c) explicitly say "I don't have enough information in the provided sources to answer that." when context is insufficient — never use outside knowledge. Grading prompts force `format="json"` and `temperature=0.0`.
### 6.12 `app/generation/citations.py`
**Build:** Convert inline `[n]` markers + the context list into structured citations; optional sentence attribution.
**Key functions:**
```python
@dataclass
class Citation: marker: int; document_id: UUID; chunk_id: UUID
    char_start: int; char_end: int; page_number: int | None; snippet: str
def build_citations(answer: str, contexts: list[Candidate]) -> tuple[str, list[Citation]]: ...
def attribute_sentences(answer: str, contexts: list[Candidate], embedder: Embedder) -> list[Citation]: ...  # optional, cosine sentence↔chunk
```
**Rules:** Every `[n]` in the answer must resolve to a context → `Citation` carrying that context's `document_id/chunk_id/offsets`. If the answer asserts facts but contains zero markers, `finalize` flags it as ungrounded (treat as faithfulness failure). Snippet = first ~200 chars of the cited chunk. Sentence attribution is best-effort and additive; never blocks the response.
### 6.13 `app/graph/state.py`
**Build:** The graph state object threaded through nodes.
```python
class GraphState(TypedDict, total=False):
    query: str
    user_id: str
    user_roles: list[str]
    candidates: list[Candidate]          # post-hybrid
    reranked: list[Candidate]            # post-rerank, fed to generation
    doc_grades: list[dict]               # CRAG per-doc {relevant, score}
    needs_correction: bool
    correction_attempts: int
    answer: str
    citations: list[Citation]
    faithfulness_score: float
    faithful: bool
    regen_attempts: int
    insufficient_evidence: bool
    audit_request_id: str
```
### 6.14 `app/graph/nodes/*` + `app/graph/pipeline.py`
**Build each node as a pure-ish function** `(state) -> partial state`, plus conditional routers, then compile.
- **`retrieve.py`** → calls `hybrid_retrieve`; sets `candidates`. If empty → set `insufficient_evidence=True`.
- **`rerank.py`** → `reranker.rerank`; sets `reranked`.
- **`grade_documents.py` (CRAG)** → for each reranked doc, call `doc_relevance_prompt` (JSON, temp 0). Compute mean score; set `doc_grades`. If `mean < CRAG_RELEVANCE_THRESHOLD` OR `count(relevant) < CRAG_MIN_RELEVANT_DOCS` → `needs_correction=True`; drop docs graded irrelevant from `reranked`.
- **`transform_query.py`** → only entered on the corrective path: rewrite the query via `query_rewrite_prompt`, increment `correction_attempts`, route back to `retrieve`. **Never** triggers a web search.
- **`generate.py`** → `generation_prompt` over `reranked`; sets `answer`.
- **`grade_faithfulness.py`** → `faithfulness_prompt` (JSON, temp 0); set `faithfulness_score`, `faithful = score >= FAITHFULNESS_THRESHOLD`.
- **`finalize.py`** → `build_citations`; if no citations but factual claims present → mark unfaithful; assemble the response payload; (caller writes `query_log` + audit).
**Graph wiring (`pipeline.py`):**
```python
def build_graph():
    g = StateGraph(GraphState)
    g.add_node("retrieve", retrieve_node)
    g.add_node("rerank", rerank_node)
    g.add_node("grade_documents", grade_documents_node)
    g.add_node("transform_query", transform_query_node)
    g.add_node("generate", generate_node)
    g.add_node("grade_faithfulness", grade_faithfulness_node)
    g.add_node("finalize", finalize_node)
    g.add_edge(START, "retrieve")
    g.add_conditional_edges("retrieve",
        lambda s: "empty" if s.get("insufficient_evidence") else "ok",
        {"empty": "finalize", "ok": "rerank"})
    g.add_edge("rerank", "grade_documents")
    g.add_conditional_edges("grade_documents", route_after_crag,
        {"correct": "transform_query", "generate": "generate"})
    g.add_conditional_edges("transform_query", route_after_transform,
        {"retry": "retrieve", "giveup": "generate"})   # giveup when correction_attempts > MAX_CORRECTION_ATTEMPTS
    g.add_edge("generate", "grade_faithfulness")
    g.add_conditional_edges("grade_faithfulness", route_after_faithfulness,
        {"regen": "generate", "done": "finalize"})       # regen until MAX_REGEN_ATTEMPTS, then finalize honestly
    g.add_edge("finalize", END)
    return g.compile()
```
**Rules:** Routers must terminate (respect `MAX_CORRECTION_ATTEMPTS`, `MAX_REGEN_ATTEMPTS`). On give-up with low faithfulness, `finalize` returns the answer **flagged** `faithful=false` plus an explicit caveat, or an "insufficient evidence" response — never a confident unsupported answer.
### 6.15 `app/audit/`
**Build:** Tamper-evident hash chain, append logger, verifier.
**Key functions:**
```python
# hash_chain.py
def canonicalize(entry: dict) -> bytes: ...                 # deterministic JSON (sorted keys, no whitespace, UTC iso)
def compute_entry_hash(payload: dict, prev_hash: str, hmac_key: str) -> str:
    body = canonicalize(payload) + prev_hash.encode()
    return hmac.new(hmac_key.encode(), body, hashlib.sha256).hexdigest()
# logger.py
async def write_audit(db, *, actor_id: UUID | None, actor_roles: list[str], action: str,
                      resource_type: str, resource_id: str | None, outcome: Literal["success","denied","error"],
                      ip: str | None, request_id: str, details: dict) -> AuditLog: ...
# verifier.py
async def verify_chain(db, start_id: int = 0) -> ChainReport: ...   # recomputes each link; reports first break
```
**Business rules:**
- Each new entry links to the previous entry's `entry_hash` (or `AUDIT_CHAIN_GENESIS_HASH` for the first). `entry_hash = compute_entry_hash(payload, prev_hash, AUDIT_HMAC_KEY)`.
- Append is **fail-closed**: if the audit write fails, the triggering operation fails. Audit table is append-only — grant the app's audit path `INSERT, SELECT` only (no `UPDATE/DELETE`) via the `aegis_audit` DB role (`init.sql`).
- Audited actions (minimum): `auth.login`, `auth.login_failed`, `auth.refresh`, `auth.logout`, `document.ingested`, `document.deleted`, `query.executed`, `query.denied`, `role.assigned`, `role.revoked`, `audit.verified`, `eval.run`.
- `verify_chain` recomputes hashes sequentially and returns `{ok, total, first_broken_id, broken_field}`.
### 6.16 `app/eval/`
**Build:** Local-model wiring + RAGAS + DeepEval runners + CI gate.
**Key functions:**
```python
# local_llm.py
def get_ragas_llm(): ...            # langchain_community ChatOllama(base_url=OLLAMA_HOST, model=OLLAMA_MODEL, temperature=0)
def get_ragas_embeddings(): ...     # local BGE-M3 wrapped as a langchain Embeddings
def get_deepeval_model(): ...       # DeepEval custom LLM backed by Ollama
# ragas_runner.py
def run_ragas(dataset_path: str) -> RagasResult: ...    # faithfulness, answer_relevancy, context_precision, context_recall
# deepeval_runner.py
def run_deepeval(dataset_path: str) -> DeepEvalResult: ...   # hallucination, faithfulness, answer_relevancy
```
**Rules:** **Never** let RAGAS/DeepEval fall back to OpenAI — explicitly pass the local LLM + embeddings to every metric. Dataset format `golden_qa.jsonl`: `{"question","ground_truth","contexts":[...]}` (contexts optional; if absent, run the live pipeline to produce them). `eval/ci_gate.py` exits non-zero if `faithfulness < FAITHFULNESS_THRESHOLD` or `hallucination_rate > (1 - FAITHFULNESS_THRESHOLD)`.
### 6.17 `app/api/v1/` (routers)
**Build:** Thin routers that validate input, enforce auth/roles, call services, write audit, return DTOs. See Section 7 for the full contract. No business logic in routers.
### 6.18 `frontend/`
**Build:**
- `api/client.ts`: fetch wrapper attaching `Authorization: Bearer`; on 401 → call refresh once → retry; on refresh failure → clear store → route to `/login`. Base URL from `VITE_API_BASE_URL`.
- `store/authStore.ts` (Zustand): `{ accessToken, refreshToken, user, roles, login(), logout() }`.
- **Login** → **Chat** (message list, input, streaming via `useQueryStream`; an **EvidencePanel** showing retrieved chunks, CRAG doc grades, faithfulness score; **CitationChip**s under each answer that, on click, reveal the cited snippet + document + page). **Documents** (list filtered server-side by RBAC; upload dialog with classification + allowed-roles selectors — only roles ≤ the uploader's authority). **Audit** (paginated table + a "Verify chain" button calling `/audit/verify`, showing OK/broken). **Eval** (trigger run, list runs, show metric cards).
**Rules:** Strict TS; types in `types/api.ts` mirror backend DTOs exactly. Never store tokens in `localStorage` in plaintext if avoidable — keep in memory (Zustand) + httpOnly cookie option noted in README. Show explicit UI state for `insufficient_evidence` and `faithful=false` (do not render a low-faithfulness answer as if trusted).
### 6.19 `infra/`
**Build:** `nginx.conf` (proxy `/api` → backend, serve static frontend, set security headers), `postgres/init.sql` (create `aegis_audit` role with INSERT/SELECT-only grant on `audit_log`; enable needed extensions), `scripts/download_models.sh` + `pull_ollama_model.sh` (the only online steps), `seed_admin.py`. `docker-compose.airgap.yml` overlay removes all published ports except nginx and sets `dns: []` / internal networks to prove no egress.
---
## 7. All API Endpoints
Base path `/api/v1`. All requests/responses JSON unless noted. All non-auth routes require a valid bearer token. Errors use a uniform shape: `{ "error": { "code": str, "message": str, "request_id": str } }`. Every sensitive call writes an audit record.
**Auth**
| Method | Path | Auth | Request | Response (200) |
|---|---|---|---|---|
| POST | `/auth/login` | none | `{username, password}` | `{access_token, refresh_token, token_type:"bearer", user:{id,username,roles}}` |
| POST | `/auth/refresh` | refresh token | `{refresh_token}` | `{access_token, refresh_token, token_type}` |
| POST | `/auth/logout` | bearer | `{}` | `{status:"ok"}` (revokes refresh token) |
| GET | `/auth/me` | bearer | – | `{id, username, email, roles, is_active}` |
**Documents** (RBAC-filtered)
| Method | Path | Roles | Request | Response |
|---|---|---|---|---|
| POST | `/documents` | analyst, admin | multipart: `file`, `classification`, `allowed_roles[]` | `201 {id, filename, classification, allowed_roles, chunk_count, status}` |
| GET | `/documents` | any | query: `page,size,classification?` | `200 {items:[DocumentSummary], total, page, size}` (only visible docs) |
| GET | `/documents/{id}` | any (if visible) | – | `200 DocumentDetail` or `403/404` |
| DELETE | `/documents/{id}` | admin | – | `200 {status:"deleted"}` (removes chunks + FAISS ids + rebuilds BM25) |
| POST | `/documents/{id}/reindex` | admin | `{}` | `202 {status:"reindexing"}` |
**Query**
| Method | Path | Roles | Request | Response |
|---|---|---|---|---|
| POST | `/query` | any | `{query: str, top_k?: int}` | `200 QueryResponse` |
| POST | `/query/stream` | any | `{query: str}` | `text/event-stream` (SSE) tokens, then a final `event: done` with `QueryResponse` |
`QueryResponse`:
```json
{
  "answer": "string",
  "insufficient_evidence": false,
  "faithful": true,
  "faithfulness_score": 0.86,
  "citations": [
    {"marker":1,"document_id":"uuid","chunk_id":"uuid","page_number":4,
     "char_start":1203,"char_end":1487,"snippet":"..."}
  ],
  "retrieved_chunks": [
    {"chunk_id":"uuid","document_id":"uuid","score":0.71,"page_number":4,"content_preview":"..."}
  ],
  "doc_grades": [{"chunk_id":"uuid","relevant":true,"score":0.9}],
  "correction_applied": false,
  "latency_ms": 4210,
  "request_id":"uuid"
}
```
**Audit** (compliance_auditor, admin)
| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/audit` | query: `page,size,actor_id?,action?,from?,to?` | `200 {items:[AuditEntry], total, page, size}` |
| GET | `/audit/verify` | query: `start_id?` | `200 {ok:bool, total:int, first_broken_id:int|null, broken_field:str|null}` |
| GET | `/audit/export` | query: `from?,to?,format=jsonl` | `200` file stream (append-only export) |
**Eval** (admin)
| Method | Path | Request | Response |
|---|---|---|---|
| POST | `/eval/run` | `{dataset?: str, suite: "ragas"|"deepeval"|"both"}` | `202 {run_id}` |
| GET | `/eval/runs` | query: `page,size` | `200 {items:[EvalRunSummary], total}` |
| GET | `/eval/runs/{id}` | – | `200 EvalRunDetail (metrics, thresholds, passed)` |
**Admin / RBAC** (admin)
| Method | Path | Request | Response |
|---|---|---|---|
| POST | `/admin/users` | `{username,email,password,roles[]}` | `201 UserSummary` |
| GET | `/admin/users` | `page,size` | `200 {items:[UserSummary],total}` |
| POST | `/admin/users/{id}/roles` | `{add:[],remove:[]}` | `200 UserSummary` (audited as role.assigned/revoked) |
| POST | `/admin/roles` | `{name,description}` | `201 RoleSummary` |
**Health**
| Method | Path | Auth | Response |
|---|---|---|---|
| GET | `/health` | none | `200 {status:"ok"}` (liveness) |
| GET | `/health/ready` | none | `200 {db:bool, ollama:bool, faiss:bool, embedder:bool, reranker:bool}` (readiness; 503 if any false) |
---
## 8. Database Schema
PostgreSQL 16. UUID PKs (`gen_random_uuid()` via `pgcrypto`) except `audit_log` (BIGSERIAL for monotonic ordering). Manage with Alembic; the baseline migration creates all tables below. `init.sql` enables `pgcrypto` and creates the restricted audit role.
**users**
| column | type | notes |
|---|---|---|
| id | UUID PK | default gen_random_uuid() |
| username | TEXT UNIQUE NOT NULL | |
| email | TEXT UNIQUE | |
| hashed_password | TEXT NOT NULL | argon2 |
| is_active | BOOLEAN NOT NULL DEFAULT true | |
| created_at | TIMESTAMPTZ NOT NULL DEFAULT now() | |
| updated_at | TIMESTAMPTZ NOT NULL DEFAULT now() | |
**roles**
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| name | TEXT UNIQUE NOT NULL | matches `Role` enum values |
| description | TEXT | |
**user_roles** (assoc)
| column | type | notes |
|---|---|---|
| user_id | UUID FK→users.id ON DELETE CASCADE | |
| role_id | UUID FK→roles.id ON DELETE CASCADE | PK(user_id, role_id) |
**refresh_tokens**
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK→users.id ON DELETE CASCADE | |
| token_hash | TEXT NOT NULL | sha256 of token |
| expires_at | TIMESTAMPTZ NOT NULL | |
| revoked | BOOLEAN NOT NULL DEFAULT false | |
| created_at | TIMESTAMPTZ NOT NULL DEFAULT now() | |
**documents**
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| filename | TEXT NOT NULL | |
| content_hash | TEXT NOT NULL | sha256(normalized text); index |
| source_path | TEXT | stored original location |
| filetype | TEXT NOT NULL | pdf/docx/... |
| classification | TEXT NOT NULL | `Classification` enum |
| allowed_roles | TEXT[] NOT NULL | role names permitted |
| uploaded_by | UUID FK→users.id | |
| status | TEXT NOT NULL DEFAULT 'ready' | ingesting/ready/error |
| page_count | INTEGER | |
| chunk_count | INTEGER NOT NULL DEFAULT 0 | |
| metadata | JSONB NOT NULL DEFAULT '{}' | |
| created_at | TIMESTAMPTZ NOT NULL DEFAULT now() | |
| UNIQUE(content_hash, classification) | | dedupe guard |
**chunks**
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| document_id | UUID FK→documents.id ON DELETE CASCADE | index |
| chunk_index | INTEGER NOT NULL | order within doc |
| content | TEXT NOT NULL | |
| token_count | INTEGER NOT NULL | |
| page_number | INTEGER | |
| char_start | INTEGER NOT NULL | offset into normalized source |
| char_end | INTEGER NOT NULL | |
| faiss_id | BIGINT UNIQUE NOT NULL | maps to FAISS + BM25 row |
| embedding_model | TEXT NOT NULL | e.g. bge-m3 |
| created_at | TIMESTAMPTZ NOT NULL DEFAULT now() | |
(Optional: a `pgvector` `embedding VECTOR(1024)` column as a cold backup of FAISS — only if `pgvector` is provisioned. FAISS remains the live index.)
**query_log**
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK→users.id | |
| query_text | TEXT NOT NULL | |
| retrieved_chunk_ids | UUID[] NOT NULL DEFAULT '{}' | |
| answer_text | TEXT | |
| citations | JSONB NOT NULL DEFAULT '[]' | |
| faithfulness_score | NUMERIC(4,3) | |
| faithful | BOOLEAN | |
| insufficient_evidence | BOOLEAN NOT NULL DEFAULT false | |
| correction_applied | BOOLEAN NOT NULL DEFAULT false | |
| latency_ms | INTEGER | |
| created_at | TIMESTAMPTZ NOT NULL DEFAULT now() | |
**audit_log** (append-only)
| column | type | notes |
|---|---|---|
| id | BIGSERIAL PK | monotonic order = chain order |
| ts | TIMESTAMPTZ NOT NULL DEFAULT now() | |
| actor_id | UUID NULL | null for pre-auth events |
| actor_roles | TEXT[] NOT NULL DEFAULT '{}' | |
| action | TEXT NOT NULL | e.g. query.executed |
| resource_type | TEXT NOT NULL | document/query/role/... |
| resource_id | TEXT | |
| outcome | TEXT NOT NULL | success/denied/error |
| ip_address | INET | |
| request_id | UUID NOT NULL | correlation id |
| details | JSONB NOT NULL DEFAULT '{}' | |
| prev_hash | TEXT NOT NULL | previous entry_hash |
| entry_hash | TEXT NOT NULL | HMAC-SHA256 link |
Grants (init.sql): `aegis_audit` role → `INSERT, SELECT` on `audit_log` only; **revoke** `UPDATE, DELETE` from all app roles. Optionally enforce append-only with a `BEFORE UPDATE/DELETE` trigger that raises.
**eval_runs**
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| run_label | TEXT | |
| suite | TEXT NOT NULL | ragas/deepeval/both |
| dataset | TEXT NOT NULL | |
| metrics | JSONB NOT NULL DEFAULT '{}' | per-metric scores |
| faithfulness_avg | NUMERIC(4,3) | |
| answer_relevancy_avg | NUMERIC(4,3) | |
| context_precision_avg | NUMERIC(4,3) | |
| hallucination_rate | NUMERIC(4,3) | |
| passed | BOOLEAN NOT NULL DEFAULT false | vs thresholds |
| commit_sha | TEXT | |
| created_at | TIMESTAMPTZ NOT NULL DEFAULT now() | |
---
## 9. Constraints / Do Not Do
**Hard NOs (any violation = reject the change):**
- ❌ No external network calls at runtime. No OpenAI/Anthropic/HF Hub/CDN/telemetry. (RAGAS/DeepEval default to OpenAI — you MUST override to local.)
- ❌ No `pip install` / `npm install` / model download at request time. Provisioning is a separate, explicit, online-only step.
- ❌ No RBAC enforcement only at the API. It MUST also gate the retrieval candidate set. No post-hoc filtering of an answer that was generated over forbidden context.
- ❌ No answer without citations when factual claims are made. No fabricated citations or fabricated facts.
- ❌ No CRAG web-search fallback. Correction = internal query rewrite + re-retrieval, or graceful "insufficient evidence".
- ❌ No mutable audit log. No `UPDATE`/`DELETE` on `audit_log`. No bypassing the audit writer from application code.
- ❌ No secrets in code, logs, or the repo. No logging of full document contents, full prompts with PII, or tokens.
- ❌ No `Any`/`any` across module boundaries. No untyped JSON blobs as function contracts.
- ❌ No global mutable state for models except the documented `@lru_cache` singletons loaded in the lifespan.
- ❌ No swallowing exceptions on auth/RBAC/audit paths. Fail closed, then log.
**Do:**
- ✅ Pin versions. Deterministic builds.
- ✅ `temperature=0.0` for all grading/faithfulness LLM calls.
- ✅ Wrap multi-write operations (ingestion, delete) in transactions with FAISS/BM25 compensation.
- ✅ Keep routers thin; put logic in services/modules.
- ✅ Write the tests named in `tests/` as you build each module.
---
## 10. Definition of Done (Per Module)
A module is "done" only when all its boxes pass. CI must be green.
**Config (6.1):** App refuses to boot in `production` with any placeholder/missing secret; `get_settings()` cached; `DATABASE_URL` built from parts. Unit test asserts placeholder rejection.
**DB + models (6.2):** `alembic upgrade head` creates every table in Section 8 with correct types/constraints; `aegis_audit` role has INSERT/SELECT-only on `audit_log`; `seed_admin.py` creates the four default roles + one admin. Integration test connects and round-trips a user.
**Auth + RBAC (6.3):** Login returns valid access+refresh; expired/invalid token → 401; `require_roles` blocks unauthorized roles → 403 (audited as denied). `tests/unit/test_rbac.py`: `is_document_visible` truth table for all role×classification combos; admin sees all; empty-on-error.
**Audit (6.15):** Appending N entries produces a verifiable chain; `verify_chain` returns `ok=true`; mutating any stored `details`/`entry_hash` makes `verify_chain` report the exact `first_broken_id`. `tests/unit/test_hash_chain.py` + `tests/integration/test_audit_verify.py` pass. Audit write failure aborts the triggering op.
**Embeddings/FAISS/BM25 (6.5–6.7):** `embedder.encode` returns `(n,1024)` float32 L2-normalized; FAISS add/search round-trips ids; BM25 search returns ids; both honor `allowed_faiss_ids`. Save/load persists across restart.
**Ingestion (6.4):** Uploading a PDF/DOCX/TXT yields chunks with monotonic `char_start<char_end`, correct `page_number`, persisted `faiss_id`, FAISS+BM25 updated, `document.ingested` audit emitted; duplicate (same hash+classification) is deduped. Failure rolls back FAISS additions. `tests/integration/test_ingestion.py` passes.
**Hybrid + reranker (6.8–6.10):** `tests/unit/test_rrf.py` matches the reference RRF exactly. RBAC isolation test: a `viewer` querying a corpus that contains a `restricted` doc never receives that doc in `candidates`, `reranked`, or citations. Reranker reorders and truncates to `RERANK_TOP_N`.
**Generation + citations (6.11–6.12):** Generation answers only from context and emits `[n]` markers; `build_citations` resolves every marker to a real chunk with offsets; an answer with claims but no markers is flagged ungrounded.
**Graph (6.13–6.14):** `build_graph().invoke(state)` runs end-to-end; low-relevance retrieval triggers exactly one correction round then proceeds; low faithfulness triggers ≤`MAX_REGEN_ATTEMPTS` regen then finalizes with `faithful=false`; empty allowed set returns `insufficient_evidence=true`. Each query writes one `query_log` row + one `query.executed` (or `query.denied`) audit row. `tests/integration/test_query_pipeline.py` passes.
**API (6.17 / Section 7):** Every endpoint returns the documented shape; OpenAPI docs generate; role gates enforced; uniform error envelope with `request_id`. `tests/integration/test_auth_flow.py` passes.
**Eval (6.16):** `eval/ci_gate.py` runs RAGAS + DeepEval **against local Ollama + local embeddings** (verified: zero outbound connections), writes an `eval_runs` row, and exits non-zero when below thresholds. CI job runs it on a tiny golden set.
**Frontend (6.18):** Login → token flow with silent refresh on 401; Chat streams answers, renders citation chips (click → snippet+source+page) and the EvidencePanel (grades + faithfulness + retrieved chunks); Documents list is RBAC-filtered server-side and upload enforces classification + allowed-roles; Audit page verifies the chain; `insufficient_evidence` and `faithful=false` have distinct, non-misleading UI states. `tsc --noEmit` clean; build succeeds.
**Infra (6.19):** `docker-compose up` brings up postgres + ollama + backend + frontend(nginx); `/health/ready` returns all-true after models load; `docker-compose.airgap.yml` overlay runs with no external DNS/ports and the full query path still works. README documents the one-time online provisioning (`download_models.sh`, `pull_ollama_model.sh`, `seed_admin.py`).
**Whole system (acceptance):** A fresh checkout, after provisioning, can: create an admin, ingest a document with a classification, log in as a lesser role, query it, and either receive a cited+faithful answer or an explicit insufficient-evidence response — with a tamper-evident audit trail that `verify_chain` confirms intact — all with the network overlay proving zero egress.
---
## 11. Appendix — Compliance Field Mapping (reference)
Use this when writing `docs/compliance-mapping.md` and when deciding what to audit/log.
- **HIPAA §164.312(b) (Audit controls):** `audit_log` append-only hash chain; `query.executed`/`document.*` records with actor, resource, outcome, timestamp; `verify_chain` integrity attestation.
- **EU AI Act Art. 12 (Record-keeping / logging):** automatic event logging over the system's lifecycle → `audit_log` + `query_log`. Art. 13 (Transparency): citations + faithfulness score + EvidencePanel expose the basis of each answer to the user.
- **DORA (ICT risk, logging, resilience):** structured logs, audit trail, health/readiness probes, deterministic offline operation (no third-party ICT dependency at runtime).
- **GDPR / FADP / PDPL (data minimization, locality):** all processing on-premise; no data egress; least-privilege DB roles; document classification + RBAC restrict access; logs avoid storing PII payloads.
- **DIFC Reg 10 / FINMA:** auditable access control and tamper-evident records; admin role separation; exportable audit (`/audit/export`).
> When in doubt about whether to log something: if it grants access to, modifies, or produces regulated content, log it (fail-closed). Map each new audited action to at least one framework above in `compliance-mapping.md`.
