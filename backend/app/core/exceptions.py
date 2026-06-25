"""Application error hierarchy + handlers (CLAUDE.md §6, exceptions.py).

Every error response uses the uniform envelope from §7:

    {"error": {"code": str, "message": str, "request_id": str}}

Auth/RBAC/audit paths must fail closed (Golden Rule 9): raise a typed AppError,
let the handler log and return the envelope — never leak internals or stack
traces to the client.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import REQUEST_ID_HEADER, get_logger

logger = get_logger("app.error")


class AppError(Exception):
    """Base class for all application errors.

    Subclasses set ``status_code`` and ``code``; ``message`` is safe to surface
    to the caller.
    """

    status_code: int = 500
    code: str = "internal_error"

    def __init__(
        self, message: str | None = None, *, details: dict[str, Any] | None = None
    ) -> None:
        self.message = message or self.__class__.__doc__ or "An error occurred."
        self.details = details or {}
        super().__init__(self.message)


class AuthError(AppError):
    """Authentication failed or credentials are invalid."""

    status_code = 401
    code = "unauthorized"


class TokenError(AuthError):
    """The provided token is missing, expired, or invalid."""

    code = "invalid_token"


class ForbiddenError(AppError):
    """The caller's roles do not permit this action."""

    status_code = 403
    code = "forbidden"


class NotFoundError(AppError):
    """The requested resource does not exist or is not visible."""

    status_code = 404
    code = "not_found"


class ValidationAppError(AppError):
    """The request payload failed validation."""

    status_code = 422
    code = "validation_error"


class ConflictError(AppError):
    """The request conflicts with current state (e.g. duplicate)."""

    status_code = 409
    code = "conflict"


class RateLimitError(AppError):
    """The caller exceeded the allowed request rate."""

    status_code = 429
    code = "rate_limited"


class AuditIntegrityError(AppError):
    """An audit write failed; the triggering operation must fail closed."""

    status_code = 500
    code = "audit_integrity_error"


class InsufficientEvidenceError(AppError):
    """Retrieval/correction could not ground an answer (no fabrication)."""

    status_code = 422
    code = "insufficient_evidence"


def _request_id(request: Request) -> str:
    rid = getattr(request.state, "request_id", None)
    if rid:
        return str(rid)
    return request.headers.get(REQUEST_ID_HEADER, "unknown")


def _envelope(code: str, message: str, request_id: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "request_id": request_id}}


def register_exception_handlers(app: FastAPI) -> None:
    """Attach handlers that render the uniform error envelope."""

    @app.exception_handler(AppError)
    async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        rid = _request_id(request)
        logger.warning(
            "app_error",
            code=exc.code,
            status_code=exc.status_code,
            message=exc.message,
            path=request.url.path,
            request_id=rid,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, rid),
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        rid = _request_id(request)
        logger.info("validation_error", path=request.url.path, request_id=rid)
        return JSONResponse(
            status_code=422,
            content=_envelope("validation_error", "Request validation failed.", rid),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        rid = _request_id(request)
        detail = exc.detail if isinstance(exc.detail, str) else "HTTP error."
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope("http_error", detail, rid),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        rid = _request_id(request)
        # Log the type only — never leak the message/stack to the client.
        logger.error(
            "unhandled_exception",
            error_type=type(exc).__name__,
            path=request.url.path,
            request_id=rid,
        )
        return JSONResponse(
            status_code=500,
            content=_envelope("internal_error", "An internal error occurred.", rid),
        )
