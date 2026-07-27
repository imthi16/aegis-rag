"""Health & readiness probes (CLAUDE.md §7, Health).

``GET /health``       — liveness, always 200 ``{"status":"ok"}``.
``GET /health/ready`` — readiness, reports {db, ollama, faiss, embedder,
                        reranker}; returns 503 until every dependency is up.

The model components report the state of their ``@lru_cache`` singletons, which
``app.main`` loads once in the lifespan — so this flips to 200 after startup
completes rather than after the first query. ``/health`` (not ``/health/ready``)
is what container healthchecks target during bring-up, since model loading can
outlast a healthcheck start period.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", summary="Liveness probe")
async def health() -> dict[str, str]:
    return {"status": "ok"}


async def _check_db() -> bool:
    try:
        from app.db.session import ping_db

        return bool(await ping_db())
    except Exception:
        return False


async def _check_ollama() -> bool:
    try:
        from app.generation.llm import ping_llm

        return bool(await ping_llm())
    except Exception:
        return False


async def _check_faiss() -> bool:
    try:
        from app.retrieval.faiss_store import is_ready

        return bool(is_ready())
    except Exception:
        return False


async def _check_embedder() -> bool:
    try:
        from app.embeddings.embedder import is_ready

        return bool(is_ready())
    except Exception:
        return False


async def _check_reranker() -> bool:
    try:
        from app.retrieval.reranker import is_ready

        return bool(is_ready())
    except Exception:
        return False


@router.get("/ready", summary="Readiness probe")
async def ready() -> JSONResponse:
    checks = {
        "db": await _check_db(),
        "ollama": await _check_ollama(),
        "faiss": await _check_faiss(),
        "embedder": await _check_embedder(),
        "reranker": await _check_reranker(),
    }
    status_code = 200 if all(checks.values()) else 503
    return JSONResponse(status_code=status_code, content=checks)
