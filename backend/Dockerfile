# Aegis RAG backend image (CLAUDE.md §2, §6.19).
# Dependencies are installed at BUILD time only — never at runtime (Golden
# Rule 1). The running container makes no outbound calls outside the compose
# network.
FROM python:3.11-slim AS base

# Offline-by-env: pinned so transformers/FlagEmbedding never reach the Hub.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    HF_DATASETS_OFFLINE=1

WORKDIR /app

# System libs needed by PyMuPDF / faiss / argon2 at runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first for layer caching.
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# App source.
COPY . .

# Non-root runtime user.
RUN useradd --create-home --uid 10001 aegis \
    && chown -R aegis:aegis /app
USER aegis

EXPOSE 8000

# Liveness probe targets the always-on /health endpoint.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -fsS http://localhost:8000/api/v1/health || exit 1

# Dev/default command. Production uses gunicorn with uvicorn workers (see
# docker-compose / README).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
