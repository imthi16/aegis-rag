"""Seed default roles + the first admin user (CLAUDE.md §6.19, §10 DoD).

Creates the four default roles (admin, compliance_auditor, analyst, viewer) and
one admin account. Credentials come from the environment, never hardcoded:

    SEED_ADMIN_USERNAME   (default: "admin")
    SEED_ADMIN_PASSWORD   (required — refuses to run without it)
    SEED_ADMIN_EMAIL      (optional)

Idempotent: re-running adds only what is missing. Run during provisioning:

    python infra/scripts/seed_admin.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Make the backend package importable whether run from the repo root or copied
# into the backend image.
_BACKEND = Path(__file__).resolve().parents[2] / "backend"
if _BACKEND.is_dir() and str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from sqlalchemy import select  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db.models import Role, User  # noqa: E402
from app.db.session import AsyncSessionLocal, dispose_engines  # noqa: E402

DEFAULT_ROLES: list[tuple[str, str]] = [
    ("admin", "Full administrative access; sees all documents."),
    ("compliance_auditor", "Reads audit trail and metadata."),
    ("analyst", "Uploads and queries documents."),
    ("viewer", "Queries documents."),
]


async def _ensure_roles(session) -> dict[str, Role]:  # type: ignore[no-untyped-def]
    existing = {r.name: r for r in (await session.execute(select(Role))).scalars()}
    for name, description in DEFAULT_ROLES:
        if name not in existing:
            role = Role(name=name, description=description)
            session.add(role)
            existing[name] = role
            print(f"  + role: {name}")
    await session.flush()
    return existing


async def _ensure_admin(session, roles: dict[str, Role]) -> None:  # type: ignore[no-untyped-def]
    username = os.environ.get("SEED_ADMIN_USERNAME", "admin")
    password = os.environ.get("SEED_ADMIN_PASSWORD")
    email = os.environ.get("SEED_ADMIN_EMAIL")

    if not password:
        raise SystemExit("SEED_ADMIN_PASSWORD is required (no default).")

    found = (
        await session.execute(select(User).where(User.username == username))
    ).scalar_one_or_none()
    if found is not None:
        print(f"  = admin '{username}' already exists; leaving as-is.")
        return

    admin = User(
        username=username,
        email=email,
        hashed_password=hash_password(password),
        is_active=True,
        roles=[roles["admin"]],
    )
    session.add(admin)
    print(f"  + admin user: {username}")


async def main() -> int:
    print(">> Seeding default roles + first admin")
    try:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                roles = await _ensure_roles(session)
                await _ensure_admin(session, roles)
        print(">> Done.")
        return 0
    finally:
        await dispose_engines()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
