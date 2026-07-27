"""Structured logging (CLAUDE.md §6, logging.py).

structlog configured for JSON output (or console in dev), with a per-request
``request_id`` bound via contextvars and echoed on the ``X-Request-ID`` response
header. Never log secrets, tokens, or full document/PII payloads (Golden Rule:
no secrets in logs).
"""

from __future__ import annotations

import logging
import sys
import uuid
from collections.abc import Awaitable, Callable
from typing import cast

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Header used to correlate a request across logs and the audit trail.
REQUEST_ID_HEADER = "X-Request-ID"

# contextvar populated by structlog.contextvars; read by every log call.
_REQUEST_ID_KEY = "request_id"


def configure_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """Configure structlog + stdlib logging once at app startup."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if log_format == "json":
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Route stdlib logging (uvicorn, sqlalchemy, etc.) through the same level.
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger."""
    return cast("structlog.stdlib.BoundLogger", structlog.get_logger(name))


def bind_request_id(request_id: str) -> None:
    """Bind ``request_id`` into the structlog contextvars for this task."""
    structlog.contextvars.bind_contextvars(**{_REQUEST_ID_KEY: request_id})


def clear_request_id() -> None:
    structlog.contextvars.clear_contextvars()


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Generate/propagate a request id and bind it to the logging context.

    Stored on ``request.state.request_id`` so handlers and the error envelope
    (CLAUDE.md §7) can surface the same correlation id.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = request_id
        clear_request_id()
        bind_request_id(request_id)
        try:
            response = await call_next(request)
        finally:
            clear_request_id()
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
