"""Auth routes (CLAUDE.md §7 Auth).

login / refresh / logout / me. Refresh tokens are persisted only as SHA-256
hashes and rotated on use. Audit wiring (auth.login / auth.login_failed /
auth.refresh / auth.logout) is added in Step 4.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import AuthError, TokenError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_token,
    verify_password,
)
from app.db.models.user import RefreshToken, User
from app.schemas.auth import (
    LoginRequest,
    LogoutResponse,
    RefreshRequest,
    RefreshResponse,
    TokenResponse,
    UserMe,
    UserPublic,
)

router = APIRouter(prefix="/auth", tags=["auth"])


async def _persist_refresh(db: AsyncSession, user_id: uuid.UUID, token: str) -> None:
    settings = get_settings()
    expires = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_token_expire_days)
    db.add(RefreshToken(user_id=user_id, token_hash=hash_token(token), expires_at=expires))


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    result = await db.execute(
        select(User).options(selectinload(User.roles)).where(User.username == body.username)
    )
    user = result.scalar_one_or_none()

    # Same error whether the user is unknown, inactive, or the password is wrong
    # (avoid user enumeration). Audited as auth.login_failed in Step 4.
    if (
        user is None
        or not user.is_active
        or not verify_password(body.password, user.hashed_password)
    ):
        raise AuthError("Invalid credentials.")

    roles = user.role_names
    access = create_access_token(sub=str(user.id), roles=roles)
    refresh = create_refresh_token(sub=str(user.id))
    await _persist_refresh(db, user.id, refresh)
    await db.commit()

    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        user=UserPublic(id=user.id, username=user.username, roles=roles),
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)) -> RefreshResponse:
    payload = decode_token(body.refresh_token)  # raises TokenError on invalid/expired
    if payload.type != "refresh":
        raise TokenError("Not a refresh token.")

    token_hash = hash_token(body.refresh_token)
    row = (
        await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    ).scalar_one_or_none()
    if row is None or row.revoked or row.expires_at <= datetime.now(UTC):
        raise TokenError("Refresh token is revoked or expired.")
    if str(row.user_id) != payload.sub:
        raise TokenError("Refresh token does not match subject.")

    # Rotate: revoke the presented token, issue a fresh pair.
    row.revoked = True
    user = (
        await db.execute(
            select(User).options(selectinload(User.roles)).where(User.id == row.user_id)
        )
    ).scalar_one_or_none()
    if user is None or not user.is_active:
        raise TokenError("User is inactive or unknown.")

    access = create_access_token(sub=str(user.id), roles=user.role_names)
    new_refresh = create_refresh_token(sub=str(user.id))
    await _persist_refresh(db, user.id, new_refresh)
    await db.commit()

    return RefreshResponse(access_token=access, refresh_token=new_refresh)


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> LogoutResponse:
    # Revoke all active refresh tokens for the caller.
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked.is_(False))
        .values(revoked=True)
    )
    await db.commit()
    return LogoutResponse(status="ok")


@router.get("/me", response_model=UserMe)
async def me(user: User = Depends(get_current_user)) -> UserMe:
    return UserMe(
        id=user.id,
        username=user.username,
        email=user.email,
        roles=user.role_names,
        is_active=user.is_active,
    )
