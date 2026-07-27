"""Admin / RBAC management routes (CLAUDE.md §7 Admin). Role: admin only.

POST /admin/users              create user
GET  /admin/users              list users
POST /admin/users/{id}/roles   assign/revoke roles (audited)
POST /admin/roles              create role
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.audit.logger import write_audit
from app.core.dependencies import get_db, require_roles
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.core.security import hash_password
from app.db.models.role import Role as RoleModel
from app.db.models.user import User
from app.rbac.classifications import Role
from app.schemas.auth import (
    CreateRoleRequest,
    CreateUserRequest,
    RoleAssignRequest,
    RoleSummary,
    UserListResponse,
    UserSummary,
)
from app.schemas.pagination import Pagination, pagination_params

router = APIRouter(prefix="/admin", tags=["admin"])

_admin = require_roles(Role.ADMIN)


def _ctx(request: Request) -> tuple[str | None, str]:
    ip = request.client.host if request.client else None
    return ip, str(request.state.request_id)


def _user_summary(user: User) -> UserSummary:
    return UserSummary(
        id=user.id,
        username=user.username,
        email=user.email,
        roles=user.role_names,
        is_active=user.is_active,
    )


async def _count_other_admins(db: AsyncSession, *, excluding: uuid.UUID) -> int:
    """Active users other than ``excluding`` who still hold the admin role."""
    stmt = (
        select(func.count(func.distinct(User.id)))
        .select_from(User)
        .join(User.roles)
        .where(
            RoleModel.name == Role.ADMIN.value,
            User.id != excluding,
            User.is_active.is_(True),
        )
    )
    return int((await db.execute(stmt)).scalar_one())


async def _roles_by_name(db: AsyncSession, names: list[str]) -> list[RoleModel]:
    if not names:
        return []
    rows = (await db.execute(select(RoleModel).where(RoleModel.name.in_(names)))).scalars().all()
    found = {r.name for r in rows}
    missing = set(names) - found
    if missing:
        raise ValidationAppError(f"Unknown role(s): {', '.join(sorted(missing))}")
    return list(rows)


@router.post("/users", status_code=status.HTTP_201_CREATED, response_model=UserSummary)
async def create_user(
    body: CreateUserRequest,
    request: Request,
    admin: User = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> UserSummary:
    existing = await db.scalar(select(User).where(User.username == body.username))
    if existing is not None:
        raise ConflictError("Username already exists.")

    roles = await _roles_by_name(db, body.roles)
    user = User(
        username=body.username,
        email=body.email,
        hashed_password=hash_password(body.password),
        is_active=True,
        roles=roles,
    )
    db.add(user)
    await db.flush()

    ip, rid = _ctx(request)
    await write_audit(
        db,
        actor_id=admin.id,
        actor_roles=admin.role_names,
        action="role.assigned",
        resource_type="user",
        resource_id=str(user.id),
        outcome="success",
        ip=ip,
        request_id=rid,
        details={"created": True, "roles": [r.name for r in roles]},
    )
    await db.commit()
    await db.refresh(user)
    return _user_summary(user)


@router.get("/users", response_model=UserListResponse)
async def list_users(
    pg: Pagination = Depends(pagination_params),
    admin: User = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> UserListResponse:
    total = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    rows = (
        (
            await db.execute(
                select(User)
                .options(selectinload(User.roles))
                .order_by(User.created_at.desc())
                .offset(pg.offset)
                .limit(pg.size)
            )
        )
        .scalars()
        .all()
    )
    return UserListResponse(
        items=[_user_summary(u) for u in rows], total=total, page=pg.page, size=pg.size
    )


@router.post("/users/{user_id}/roles", response_model=UserSummary)
async def update_roles(
    user_id: uuid.UUID,
    body: RoleAssignRequest,
    request: Request,
    admin: User = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> UserSummary:
    user = (
        await db.execute(select(User).options(selectinload(User.roles)).where(User.id == user_id))
    ).scalar_one_or_none()
    if user is None:
        raise NotFoundError("User not found.")

    ip, rid = _ctx(request)
    current = {r.name: r for r in user.roles}

    if body.add:
        to_add = await _roles_by_name(db, body.add)
        for role in to_add:
            if role.name not in current:
                user.roles.append(role)
                current[role.name] = role
        await write_audit(
            db,
            actor_id=admin.id,
            actor_roles=admin.role_names,
            action="role.assigned",
            resource_type="user",
            resource_id=str(user.id),
            outcome="success",
            ip=ip,
            request_id=rid,
            details={"added": body.add},
        )

    if body.remove:
        remove_set = set(body.remove)
        # Never allow the last admin to be demoted: with no admin left, role and
        # document administration become impossible without direct DB access,
        # which is precisely the auditable-access-control separation §11 requires
        # for DIFC Reg 10 / FINMA. Fail closed and record the denial.
        if Role.ADMIN.value in remove_set and Role.ADMIN.value in current:
            remaining = await _count_other_admins(db, excluding=user.id)
            if remaining == 0:
                await write_audit(
                    db,
                    actor_id=admin.id,
                    actor_roles=admin.role_names,
                    action="role.revoked",
                    resource_type="user",
                    resource_id=str(user.id),
                    outcome="denied",
                    ip=ip,
                    request_id=rid,
                    details={"removed": body.remove, "reason": "last_admin"},
                )
                await db.commit()
                raise ValidationAppError(
                    "Refusing to remove the last admin role; promote another user first."
                )

        user.roles = [r for r in user.roles if r.name not in remove_set]
        await write_audit(
            db,
            actor_id=admin.id,
            actor_roles=admin.role_names,
            action="role.revoked",
            resource_type="user",
            resource_id=str(user.id),
            outcome="success",
            ip=ip,
            request_id=rid,
            details={"removed": body.remove},
        )

    await db.commit()
    await db.refresh(user)
    return _user_summary(user)


@router.post("/roles", status_code=status.HTTP_201_CREATED, response_model=RoleSummary)
async def create_role(
    body: CreateRoleRequest,
    request: Request,
    admin: User = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> RoleSummary:
    existing = await db.scalar(select(RoleModel).where(RoleModel.name == body.name))
    if existing is not None:
        raise ConflictError("Role already exists.")
    role = RoleModel(name=body.name, description=body.description)
    db.add(role)
    await db.flush()

    ip, rid = _ctx(request)
    await write_audit(
        db,
        actor_id=admin.id,
        actor_roles=admin.role_names,
        action="role.created",
        resource_type="role",
        resource_id=str(role.id),
        outcome="success",
        ip=ip,
        request_id=rid,
        details={"name": body.name},
    )
    await db.commit()
    await db.refresh(role)
    return RoleSummary(id=role.id, name=role.name, description=role.description)
