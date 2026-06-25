# Runbook — Air-Gap Provisioning

> Source: [`../CLAUDE.md`](../CLAUDE.md) §6.19, §10 (Infra). The only steps that
> touch the network are the model pulls below; everything after runs offline.

## 1. Configure secrets (offline)

```bash
cp .env.example .env
python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_hex(32))"
python -c "import secrets; print('AUDIT_HMAC_KEY=' + secrets.token_hex(32))"
# Edit .env: set JWT_SECRET_KEY, AUDIT_HMAC_KEY, POSTGRES_PASSWORD,
# AUDIT_DB_PASSWORD to real values (no CHANGE_ME_* — prod refuses to boot).
```

## 2. Stage model weights (ONLINE, one-time)

Run these on a host with internet access; they write into volumes/dirs that are
then carried into the air-gapped environment.

```bash
make models     # BGE-M3 + bge-reranker-v2-m3 -> ./models
make pull-llm   # qwen2.5:32b -> ollama volume
```

## 3. Bring up the cluster (OFFLINE)

```bash
make build
make up                 # or: make up-airgap  (zero published ports but frontend)
make migrate            # apply DB schema (Step 2+)
make seed               # default roles + first admin (Step 2+)
```

## 4. Verify

```bash
bash infra/scripts/healthcheck.sh
# Liveness 200; readiness 200 once db + models + ollama are up.
```

## 5. Prove zero egress

```bash
docker compose -f docker-compose.yml -f docker-compose.airgap.yml up -d
# Backend/postgres/ollama have no published ports and no external DNS;
# the full query path still works against in-network services only.
```

## Rollback / re-provision

- Re-running `make models` / `make pull-llm` is idempotent (re-stages weights).
- DB schema changes go through Alembic migrations (`make migrate`).
