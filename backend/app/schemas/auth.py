"""Auth request/response DTOs (CLAUDE.md §7)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserPublic(BaseModel):
    """Identity block embedded in the login response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    roles: list[str]


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserPublic


class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserMe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    email: str | None
    roles: list[str]
    is_active: bool


class LogoutResponse(BaseModel):
    status: str = "ok"
