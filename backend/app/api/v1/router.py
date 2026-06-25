"""Aggregate router mounted under ``/api/v1`` (CLAUDE.md §6.17 / §7).

Routers are added as their steps land. Step 1 wires only health; auth,
documents, query, audit, eval, and admin routers are appended by steps 3–10.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routes import audit, auth, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(audit.router)

# Wired in later steps:
#   from app.api.v1.routes import documents, query, eval, admin
#   api_router.include_router(documents.router) # Step 6
#   api_router.include_router(query.router)     # Step 9
#   api_router.include_router(eval.router)      # Step 10
#   api_router.include_router(admin.router)     # Step 3 (after audit, Step 4)
