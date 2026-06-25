# Aegis RAG

A fully **air-gapped, zero-cloud Sovereign RAG platform** for regulated
industries. Authorized users ask natural-language questions over a private
corpus and receive **citation-backed, faithfulness-graded** answers, with
**RBAC enforced at retrieval** and a **tamper-evident audit log**.

Everything — LLM inference (Qwen2.5 32B via Ollama), embeddings (BGE-M3),
reranking (bge-reranker-v2-m3), and the FAISS vector index — runs locally.
**Nothing leaves the perimeter at runtime.** See [`CLAUDE.md`](./CLAUDE.md) for
the full specification (the single source of truth for this build).

> ⚠️ **Build status:** Step 1 (scaffold + config) is complete. Later steps
> (DB, auth/RBAC, audit, retrieval, generation, graph, eval, frontend, infra
> hardening) follow the order in `CLAUDE.md` §5.

## Architecture (target)

```
client ─▶ nginx ─▶ FastAPI ─▶ LangGraph
                              ├─ hybrid retrieve (FAISS dense + BM25) ─▶ RRF
                              ├─ cross-encoder rerank
                              ├─ CRAG doc-relevance grade ─▶ (rewrite + re-retrieve)
                              ├─ grounded generation (Ollama)
                              ├─ faithfulness grade
                              └─ citation finalize
Postgres = system of record (users/roles, docs/chunks, query_log, audit_log)
FAISS    = live vector index   |   Ollama = LLM service   (all on aegis_net)
```

## One-time online provisioning

Model weights are **pre-staged** while online, then the cluster runs offline.

```bash
cp .env.example .env
# Edit .env: set real JWT_SECRET_KEY, AUDIT_HMAC_KEY, POSTGRES_PASSWORD
#   (the app refuses to boot in production while these hold CHANGE_ME_*).
python -c "import secrets; print(secrets.token_hex(32))"   # generate secrets

make models      # download BGE-M3 + bge-reranker-v2-m3 into ./models
make pull-llm    # ollama pull qwen2.5:32b into the ollama volume
```

## Run

```bash
make build
make up                  # full stack on a private bridge network
make migrate             # apply DB schema (Step 2+)
make seed                # create default roles + first admin (Step 2+)

# Zero-egress mode (no published ports except the frontend):
make up-airgap
```

- Backend liveness: `GET http://localhost:8000/api/v1/health`
- Backend readiness: `GET http://localhost:8000/api/v1/health/ready`
- API docs: `http://localhost:8000/docs`
- Frontend: `http://localhost:8080`

## Backend development

```bash
cd backend
pip install -r requirements.txt && pip install -e ".[dev]"
ruff check . && mypy app && pytest
```

## Security & compliance notes

- **Secrets** live only in `.env` (git-ignored). Tokens are kept in memory on
  the frontend (Zustand); an httpOnly-cookie option is documented for hardened
  deployments.
- **Audit log** is append-only and hash-chained; a dedicated least-privilege
  DB role (`aegis_audit`) has `INSERT, SELECT` only.
- Compliance field mapping (HIPAA, GDPR, EU AI Act, DORA, FADP/FINMA,
  PDPL/DIFC Reg 10) lives in [`docs/compliance-mapping.md`](./docs/compliance-mapping.md).

## Repository layout

See `CLAUDE.md` §3 for the authoritative tree. Top level:

| Path | Purpose |
|---|---|
| `backend/` | FastAPI app, LangGraph pipeline, retrieval/audit/eval, tests |
| `frontend/` | React + TypeScript (Vite) UI |
| `infra/` | nginx, postgres init, provisioning scripts |
| `eval/` | CI eval gate + golden datasets |
| `docs/` | architecture, compliance, threat model, runbook |
