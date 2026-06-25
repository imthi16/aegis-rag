# Aegis RAG — developer & operator entrypoints (CLAUDE.md §5).
# Most targets shell into docker compose; backend dev targets run in ./backend.

SHELL := /bin/bash
COMPOSE := docker compose
COMPOSE_AIRGAP := docker compose -f docker-compose.yml -f docker-compose.airgap.yml
BACKEND := backend

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Provisioning (ONLINE, one-time — CLAUDE.md §6.19) ───────
.PHONY: models
models: ## Pre-stage embedding + reranker weights (online step)
	bash infra/scripts/download_models.sh

.PHONY: pull-llm
pull-llm: ## Pull the Ollama LLM into the local volume (online step)
	bash infra/scripts/pull_ollama_model.sh

# ── Stack lifecycle ─────────────────────────────────────────
.PHONY: build
build: ## Build all images
	$(COMPOSE) build

.PHONY: up
up: ## Start the full stack
	$(COMPOSE) up -d

.PHONY: up-airgap
up-airgap: ## Start the stack with the zero-egress overlay
	$(COMPOSE_AIRGAP) up -d

.PHONY: down
down: ## Stop the stack
	$(COMPOSE) down

.PHONY: logs
logs: ## Tail backend logs
	$(COMPOSE) logs -f backend

.PHONY: seed
seed: ## Create default roles + first admin
	$(COMPOSE) exec backend python -m infra.scripts.seed_admin

.PHONY: migrate
migrate: ## Apply database migrations
	$(COMPOSE) exec backend alembic upgrade head

# ── Backend dev (run inside ./backend) ──────────────────────
.PHONY: install
install: ## Install backend runtime + dev deps
	cd $(BACKEND) && pip install -r requirements.txt && pip install -e ".[dev]"

.PHONY: lint
lint: ## Ruff lint
	cd $(BACKEND) && ruff check .

.PHONY: fmt
fmt: ## Ruff format
	cd $(BACKEND) && ruff format .

.PHONY: typecheck
typecheck: ## mypy strict
	cd $(BACKEND) && mypy app

.PHONY: test
test: ## Run backend tests
	cd $(BACKEND) && pytest

.PHONY: eval
eval: ## Run the CI eval gate (local models only)
	python eval/ci_gate.py
