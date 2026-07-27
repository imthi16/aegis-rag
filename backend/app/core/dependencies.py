"""FastAPI dependencies (CLAUDE.md §6.3).

``get_current_user`` validates the access token and loads the active user (with
roles eager-loaded); ``require_roles`` is a dependency factory enforcing role
gates. Fail closed: missing/invalid token → 401, insufficient role → 403.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AuthError, TokenError
from app.core.exceptions import ForbiddenError as _ForbiddenError
from app.core.security import decode_token
from app.db.models.user import User
from app.db.session import get_db
from app.rbac.classifications import Role
from app.rbac.enforcement import user_role_set

# auto_error=False so we can raise the uniform envelope ourselves.
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

__all__ = ["get_current_user", "require_roles", "get_db"]


async def get_current_user(
    token: str | None = Depends(_oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not token:
        raise TokenError("Missing bearer token.")

    payload = decode_token(token)  # raises TokenError on invalid/expired
    if payload.type != "access":
        raise TokenError("Not an access token.")

    try:
        user_id = uuid.UUID(payload.sub)
    except (ValueError, AttributeError) as exc:
        raise TokenError("Malformed token subject.") from exc

    result = await db.execute(
        select(User).options(selectinload(User.roles)).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise AuthError("Inactive or unknown user.")
    return user


def require_roles(*allowed: Role) -> Callable[..., Awaitable[User]]:
    """Dependency factory: allow only callers holding one of ``allowed`` roles."""
    allowed_set = set(allowed)

    async def _checker(user: User = Depends(get_current_user)) -> User:
        if not (user_role_set(user) & allowed_set):
            raise _ForbiddenError("Your roles do not permit this action.")
        return user

    return _checker
