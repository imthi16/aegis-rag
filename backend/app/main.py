"""FastAPI application factory (CLAUDE.md §6, main.py).

Wires logging, the offline-enforcement env, CORS, the body-size guard, rate
limiting, request-id middleware, the uniform error handlers, and the
``/api/v1`` router.

The heavy ML singletons (embedder, reranker, FAISS, LLM) are loaded **once in
the lifespan** so that (a) no request pays the model-load latency and (b)
``/api/v1/health/ready`` reports true readiness rather than "nothing has been
touched yet" (CLAUDE.md §6.5/§6.10 and the Infra Definition of Done).
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import RequestIdMiddleware, configure_logging, get_logger
from app.core.middleware import BodySizeLimitMiddleware, install_rate_limiter
from app.db.session import dispose_engines

API_V1_PREFIX = "/api/v1"


def _enforce_offline_env(settings: Settings) -> None:
    """Pin HuggingFace/Transformers offline flags before any model import.

    Golden Rules 1 & 2 (ZERO EGRESS / OFFLINE BY ENV): these must be set in the
    process environment so FlagEmbedding/transformers never reach the Hub.
    """
    os.environ.setdefault("HF_HUB_OFFLINE", settings.hf_hub_offline)
    os.environ.setdefault("TRANSFORMERS_OFFLINE", settings.transformers_offline)
    os.environ.setdefault("HF_DATASETS_OFFLINE", settings.hf_datasets_offline)


def _warm_singletons() -> None:
    """Instantiate the process-wide ML singletons (CLAUDE.md §6.5–§6.10).

    Each loader is ``@lru_cache``d, so calling it here is what makes the
    corresponding ``is_ready()`` probe true. Failures are logged and swallowed
    per-component: a missing reranker must not stop the process from booting and
    serving ``/health``, it must instead surface as ``ready=false`` for that
    component so an orchestrator holds traffic back.
    """
    logger = get_logger("app.lifespan")

    from app.embeddings.embedder import get_embedder
    from app.generation.llm import get_llm
    from app.retrieval.bm25_index import get_bm25_index
    from app.retrieval.faiss_store import get_faiss_store
    from app.retrieval.reranker import get_reranker

    for name, loader in (
        ("faiss", get_faiss_store),
        ("bm25", get_bm25_index),
        ("embedder", get_embedder),
        ("reranker", get_reranker),
        ("llm", get_llm),
    ):
        try:
            loader()
            logger.info("singleton_loaded", component=name)
        except Exception as exc:
            logger.error("singleton_load_failed", component=name, error_type=type(exc).__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    logger = get_logger("app.lifespan")
    logger.info("startup", app_env=settings.app_env, app_name=settings.app_name)
    # Load the ML singletons once, off the request path. Runs in a worker thread
    # because the loaders are blocking (torch/faiss) and would otherwise stall
    # the event loop during startup.
    await asyncio.to_thread(_warm_singletons)
    try:
        yield
    finally:
        await dispose_engines()
        logger.info("shutdown")


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""
    settings = get_settings()
    _enforce_offline_env(settings)
    configure_logging(log_level=settings.log_level, log_format=settings.log_format)

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = settings

    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # REQUEST_MAX_BODY_MB — reject oversized bodies before they are buffered.
    max_body_bytes = settings.request_max_body_mb * 1024 * 1024
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=max_body_bytes)

    # RATE_LIMIT_PER_MINUTE — per-client throttle (CLAUDE.md §2, §4).
    install_rate_limiter(app, settings)

    register_exception_handlers(app)
    app.include_router(api_router, prefix=API_V1_PREFIX)

    return app


# Module-level app for ``uvicorn app.main:app`` (factory also available via
# ``uvicorn app.main:create_app --factory``).
app = create_app()
