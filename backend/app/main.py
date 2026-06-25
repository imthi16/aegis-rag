"""FastAPI application factory (CLAUDE.md §6, main.py).

Wires logging, the offline-enforcement env, CORS, request-id middleware, the
uniform error handlers, and the ``/api/v1`` router. Heavy singletons (embedder,
reranker, FAISS, LLM) are loaded in the lifespan by later steps; Step 1 only
needs the process to boot and serve ``/api/v1/health``.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import RequestIdMiddleware, configure_logging, get_logger

API_V1_PREFIX = "/api/v1"


def _enforce_offline_env(settings: Settings) -> None:
    """Pin HuggingFace/Transformers offline flags before any model import.

    Golden Rules 1 & 2 (ZERO EGRESS / OFFLINE BY ENV): these must be set in the
    process environment so FlagEmbedding/transformers never reach the Hub.
    """
    os.environ.setdefault("HF_HUB_OFFLINE", settings.hf_hub_offline)
    os.environ.setdefault("TRANSFORMERS_OFFLINE", settings.transformers_offline)
    os.environ.setdefault("HF_DATASETS_OFFLINE", settings.hf_datasets_offline)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    logger = get_logger("app.lifespan")
    logger.info("startup", app_env=settings.app_env, app_name=settings.app_name)
    # Step 5+ load model singletons here (embedder, reranker, FAISS, BM25).
    try:
        yield
    finally:
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

    register_exception_handlers(app)
    app.include_router(api_router, prefix=API_V1_PREFIX)

    return app


# Module-level app for ``uvicorn app.main:app`` (factory also available via
# ``uvicorn app.main:create_app --factory``).
app = create_app()
