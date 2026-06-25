"""Auth routes (CLAUDE.md §7 Auth) with audit wiring (§6.15).

login / refresh / logout / me. Every sensitive event emits a hash-chained audit
record in the same transaction (fail closed). Refresh tokens are persisted only
as SHA-256 hashes and rotated on use.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.audit.logger import write_audit
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


def _ctx(request: Request) -> tuple[str | None, str]:
    ip = request.client.host if request.client else None
    return ip, str(request.state.request_id)


async def _persist_refresh(db: AsyncSession, user_id: uuid.UUID, token: str) -> None:
    settings = get_settings()
    expires = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_token_expire_days)
    db.add(RefreshToken(user_id=user_id, token_hash=hash_token(token), expires_at=expires))


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    ip, rid = _ctx(request)
    result = await db.execute(
        select(User).options(selectinload(User.roles)).where(User.username == body.username)
    )
    user = result.scalar_one_or_none()

    # Same error whether unknown/inactive/bad password (no user enumeration).
    if (
        user is None
        or not user.is_active
        or not verify_password(body.password, user.hashed_password)
    ):
        await write_audit(
            db,
            actor_id=user.id if user else None,
            actor_roles=user.role_names if user else [],
            action="auth.login_failed",
            resource_type="auth",
            resource_id=body.username,
            outcome="denied",
            ip=ip,
            request_id=rid,
            details={"username": body.username},
        )
        await db.commit()
        raise AuthError("Invalid credentials.")

    roles = user.role_names
    access = create_access_token(sub=str(user.id), roles=roles)
    refresh = create_refresh_token(sub=str(user.id))
    await _persist_refresh(db, user.id, refresh)
    await write_audit(
        db,
        actor_id=user.id,
        actor_roles=roles,
        action="auth.login",
        resource_type="auth",
        resource_id=str(user.id),
        outcome="success",
        ip=ip,
        request_id=rid,
        details={"username": user.username},
    )
    await db.commit()

    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        user=UserPublic(id=user.id, username=user.username, roles=roles),
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    body: RefreshRequest, request: Request, db: AsyncSession = Depends(get_db)
) -> RefreshResponse:
    ip, rid = _ctx(request)
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

    row.revoked = True  # rotate
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
    await write_audit(
        db,
        actor_id=user.id,
        actor_roles=user.role_names,
        action="auth.refresh",
        resource_type="auth",
        resource_id=str(user.id),
        outcome="success",
        ip=ip,
        request_id=rid,
        details={},
    )
    await db.commit()

    return RefreshResponse(access_token=access, refresh_token=new_refresh)


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LogoutResponse:
    ip, rid = _ctx(request)
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked.is_(False))
        .values(revoked=True)
    )
    await write_audit(
        db,
        actor_id=user.id,
        actor_roles=user.role_names,
        action="auth.logout",
        resource_type="auth",
        resource_id=str(user.id),
        outcome="success",
        ip=ip,
        request_id=rid,
        details={},
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
