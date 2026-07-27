#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Aegis RAG — ONLINE provisioning step (CLAUDE.md §6.19, Golden Rule 1).
#
# Pull the LLM into the Ollama volume while online, so the cluster can serve it
# offline afterwards. Runs against the `ollama` service in the compose network;
# the pull itself reaches the Ollama registry — this is provisioning, not
# runtime. After this completes, no further egress is required to answer queries.
#
# Usage:   bash infra/scripts/pull_ollama_model.sh [MODEL]
# Default MODEL: value of OLLAMA_MODEL in .env, else qwen2.5:32b
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# Load OLLAMA_MODEL from .env if present (without exporting everything).
if [[ -f .env ]]; then
  ENV_MODEL="$(grep -E '^OLLAMA_MODEL=' .env | head -n1 | cut -d= -f2- || true)"
fi
MODEL="${1:-${ENV_MODEL:-qwen2.5:32b}}"

echo ">> Aegis RAG LLM provisioning (ONLINE step)"
echo ">> Model: ${MODEL}"

if docker compose ps --services 2>/dev/null | grep -qx "ollama"; then
  echo ">> Pulling via the compose 'ollama' service..."
  docker compose up -d ollama
  # Wait for the server to accept connections.
  for _ in $(seq 1 30); do
    if docker compose exec -T ollama ollama list >/dev/null 2>&1; then
      break
    fi
    sleep 2
  done
  docker compose exec -T ollama ollama pull "${MODEL}"
elif command -v ollama >/dev/null 2>&1; then
  echo ">> Pulling via local ollama CLI..."
  ollama pull "${MODEL}"
else
  echo "!! Neither a compose 'ollama' service nor a local 'ollama' CLI was found."
  echo "   Start the stack first (make up) or install Ollama in the provisioning host."
  exit 1
fi

echo ">> Done. The model now lives in the ollama volume and serves offline."
