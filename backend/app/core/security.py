"""Password hashing + JWT encode/decode (CLAUDE.md §6.3).

Argon2 password hashing (PASSWORD_HASH_SCHEME=argon2) and HS256 JWTs signed with
JWT_SECRET_KEY. Refresh tokens are stored only as SHA-256 hashes (§8). Decoding
fails closed: any invalid/expired token raises ``TokenError`` (Golden Rule 9).

Implemented here (rather than only in Step 3) because seed_admin.py needs
hash_password to create the first admin. Auth routes/dependencies that consume
these helpers are wired in Step 3.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.exceptions import TokenError

# Argon2 only — deterministic, audited, no silent scheme drift.
_pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

TokenType = Literal["access", "refresh"]


class TokenPayload(BaseModel):
    """Decoded JWT claims (typed; no untyped dicts cross the boundary)."""

    sub: str
    type: TokenType
    roles: list[str] = []
    jti: str
    iat: int
    exp: int


# ── Password hashing ────────────────────────────────────────
def hash_password(raw: str) -> str:
    return str(_pwd_context.hash(raw))


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return bool(_pwd_context.verify(raw, hashed))
    except Exception:
        # Malformed hash, etc. — fail closed.
        return False


def hash_token(raw: str) -> str:
    """SHA-256 of a refresh token for at-rest storage (§8 refresh_tokens)."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ── JWT ─────────────────────────────────────────────────────
def _now() -> datetime:
    return datetime.now(UTC)


def _encode(claims: dict[str, object], expires: timedelta) -> str:
    settings = get_settings()
    issued = _now()
    payload = {
        **claims,
        "iat": int(issued.timestamp()),
        "exp": int((issued + expires).timestamp()),
        "jti": uuid.uuid4().hex,
    }
    return str(jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm))


def create_access_token(sub: str, roles: list[str]) -> str:
    settings = get_settings()
    return _encode(
        {"sub": sub, "type": "access", "roles": roles},
        timedelta(minutes=settings.jwt_access_token_expire_minutes),
    )


def create_refresh_token(sub: str) -> str:
    settings = get_settings()
    return _encode(
        {"sub": sub, "type": "refresh"},
        timedelta(days=settings.jwt_refresh_token_expire_days),
    )


def decode_token(token: str) -> TokenPayload:
    """Decode + validate a JWT. Raises ``TokenError`` on any problem."""
    settings = get_settings()
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return TokenPayload(**claims)
    except (JWTError, ValueError) as exc:
        raise TokenError("Invalid or expired token.") from exc
