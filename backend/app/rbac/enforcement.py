"""RBAC enforcement (CLAUDE.md §6.3, Golden Rule 3 & 9).

The authoritative access gate lives here and is applied at retrieval — never
only at the API. Every function fails closed: any error computing visibility
yields an empty allowed set / not-visible, never a default-allow.
"""

from __future__ import annotations

import uuid
from typing import Protocol, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models.document import Document
from app.db.models.user import User
from app.rbac.classifications import Role

logger = get_logger("app.rbac")


class _HasDocumentId(Protocol):
    document_id: uuid.UUID


_CandidateT = TypeVar("_CandidateT", bound=_HasDocumentId)


def user_role_set(user: User) -> set[Role]:
    """Parse a user's role names into the Role enum set (unknown names dropped)."""
    valid = {r.value for r in Role}
    return {Role(name) for name in user.role_names if name in valid}


def is_admin(user: User) -> bool:
    return Role.ADMIN in user_role_set(user)


def is_document_visible(doc: Document, user_roles: set[Role]) -> bool:
    """A doc is visible iff the user is admin or shares a role with allowed_roles.

    Pure + fail-closed: any malformed input → not visible.
    """
    try:
        if Role.ADMIN in user_roles:
            return True
        role_values = {r.value for r in user_roles}
        return bool(set(doc.allowed_roles) & role_values)
    except Exception:
        logger.warning("is_document_visible_error")
        return False


async def allowed_document_ids(db: AsyncSession, user: User) -> set[uuid.UUID]:
    """Authoritative set of document ids the user may access (RBAC gate).

    Computed from Postgres per request. Fail-closed: on any error return an
    empty set so retrieval yields nothing rather than leaking.
    """
    try:
        roles = user_role_set(user)
        if Role.ADMIN in roles:
            rows = await db.execute(select(Document.id))
            return set(rows.scalars().all())

        role_values = [r.value for r in roles]
        if not role_values:
            return set()

        # Postgres array overlap (&&): documents whose allowed_roles intersects
        # the caller's roles.
        stmt = select(Document.id).where(Document.allowed_roles.overlap(role_values))
        rows = await db.execute(stmt)
        return set(rows.scalars().all())
    except Exception:
        logger.warning("allowed_document_ids_error", user_id=str(getattr(user, "id", None)))
        return set()


def filter_chunk_candidates(
    candidates: list[_CandidateT], allowed_doc_ids: set[uuid.UUID]
) -> list[_CandidateT]:
    """Drop any candidate whose document is not in the allowed set (defense in depth)."""
    return [c for c in candidates if c.document_id in allowed_doc_ids]
