"""DB round-trip (CLAUDE.md §10 — DB + models DoD).

Connects and round-trips a user with a role. Skips when no DB is reachable
(see integration conftest); runs in CI against the postgres service.
"""

from __future__ import annotations

import pytest
from app.db.models import Role, User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_user_role_round_trip(db_session: AsyncSession) -> None:
    role = Role(name="analyst", description="Uploads and queries.")
    db_session.add(role)
    await db_session.flush()

    user = User(username="alice", hashed_password="argon2$placeholder", roles=[role])
    db_session.add(user)
    await db_session.commit()

    loaded = (await db_session.execute(select(User).where(User.username == "alice"))).scalar_one()
    await db_session.refresh(loaded)  # pull server defaults (id, is_active)

    assert loaded.id is not None
    assert loaded.is_active is True
    assert loaded.role_names == ["analyst"]


@pytest.mark.asyncio
async def test_document_unique_hash_classification(db_session: AsyncSession) -> None:
    """The (content_hash, classification) dedupe guard is enforced (§8)."""
    from app.db.models import Document
    from sqlalchemy.exc import IntegrityError

    d1 = Document(
        filename="a.pdf",
        content_hash="deadbeef",
        filetype="pdf",
        classification="internal",
        allowed_roles=["analyst"],
    )
    db_session.add(d1)
    await db_session.commit()

    dup = Document(
        filename="b.pdf",
        content_hash="deadbeef",
        filetype="pdf",
        classification="internal",
        allowed_roles=["viewer"],
    )
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()
