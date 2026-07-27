"""Aggregate router mounted under ``/api/v1`` (CLAUDE.md §6.17 / §7).

Routers are added as their steps land. Step 1 wires only health; auth,
documents, query, audit, eval, and admin routers are appended by steps 3–10.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routes import admin, audit, auth, documents, eval, health, query

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(audit.router)
api_router.include_router(documents.router)
api_router.include_router(query.router)
api_router.include_router(admin.router)
api_router.include_router(eval.router)
