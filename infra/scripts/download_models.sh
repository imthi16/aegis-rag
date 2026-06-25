#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Aegis RAG — ONLINE provisioning step (CLAUDE.md §6.19, Golden Rule 1).
#
# Pre-stage the embedding + reranker weights into ./models so the cluster can
# run fully offline afterwards. This is the ONLY place network access to a model
# hub is permitted, and it runs OUTSIDE the running cluster. The services
# themselves set HF_HUB_OFFLINE=1 and never fetch at runtime.
#
# Usage:   bash infra/scripts/download_models.sh [TARGET_DIR]
# Default TARGET_DIR: ./models  (mounted read-only into the backend at /models)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

TARGET_DIR="${1:-./models}"
EMBEDDING_REPO="BAAI/bge-m3"
RERANKER_REPO="BAAI/bge-reranker-v2-m3"
EMBEDDING_DIR="${TARGET_DIR}/bge-m3"
RERANKER_DIR="${TARGET_DIR}/bge-reranker-v2-m3"

echo ">> Aegis RAG model provisioning (ONLINE step)"
echo ">> Target directory: ${TARGET_DIR}"
mkdir -p "${EMBEDDING_DIR}" "${RERANKER_DIR}"

if ! command -v huggingface-cli >/dev/null 2>&1; then
  echo "!! huggingface-cli not found."
  echo "   Install it in your provisioning environment (NOT inside the cluster):"
  echo "     pip install 'huggingface_hub[cli]'"
  exit 1
fi

# NOTE: explicitly online here. Do not set HF_HUB_OFFLINE for this script.
echo ">> Downloading embeddings: ${EMBEDDING_REPO}"
huggingface-cli download "${EMBEDDING_REPO}" \
  --local-dir "${EMBEDDING_DIR}" \
  --local-dir-use-symlinks False

echo ">> Downloading reranker:   ${RERANKER_REPO}"
huggingface-cli download "${RERANKER_REPO}" \
  --local-dir "${RERANKER_DIR}" \
  --local-dir-use-symlinks False

echo ">> Done. Verify the paths match your .env:"
echo "     EMBEDDING_MODEL_PATH=/models/bge-m3"
echo "     RERANKER_MODEL_PATH=/models/bge-reranker-v2-m3"
echo ">> After staging, the cluster runs OFFLINE — no further hub access."
