"""Request-guard middleware: body-size limit + rate limiting (CLAUDE.md §2, §4).

Both guards render the uniform §7 error envelope so a throttled or oversized
request looks like every other error to the client.

``RATE_LIMIT_PER_MINUTE`` is enforced with ``slowapi`` as a global default limit
applied via middleware, so a newly added router cannot forget to opt in — the
throttle is a property of the app, not of each endpoint. Liveness/readiness
probes are explicitly exempted so an orchestrator never mistakes a 429 for an
outage.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.config import Settings
from app.core.logging import REQUEST_ID_HEADER, get_logger

logger = get_logger("app.middleware")


def _request_id(request: Request) -> str:
    rid = getattr(request.state, "request_id", None)
    if rid:
        return str(rid)
    return request.headers.get(REQUEST_ID_HEADER, "unknown")


def _envelope(code: str, message: str, request_id: str) -> dict[str, dict[str, str]]:
    return {"error": {"code": code, "message": message, "request_id": request_id}}


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests whose body exceeds ``REQUEST_MAX_BODY_MB``.

    Checks ``Content-Length`` up front so an oversized upload is refused before
    the body is buffered. Requests without a declared length pass through — the
    per-route upload check (``UPLOAD_MAX_SIZE_MB``) is the backstop for chunked
    bodies.
    """

    def __init__(self, app: FastAPI, max_bytes: int) -> None:
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        raw_length = request.headers.get("content-length")
        if raw_length is not None:
            try:
                declared = int(raw_length)
            except ValueError:
                declared = -1
            if declared > self.max_bytes:
                rid = _request_id(request)
                logger.warning(
                    "body_too_large",
                    declared_bytes=declared,
                    max_bytes=self.max_bytes,
                    path=request.url.path,
                    request_id=rid,
                )
                return JSONResponse(
                    status_code=413,
                    content=_envelope(
                        "body_too_large",
                        "Request body exceeds the configured maximum size.",
                        rid,
                    ),
                )
        return await call_next(request)


def rate_limit_key(request: Request) -> str:
    """Per-client throttle key.

    The backend only ever receives traffic through the in-network nginx, which
    overwrites ``X-Real-IP`` with the true peer address on every proxied request
    (``infra/nginx/nginx.conf``). Reading it is therefore not client-spoofable
    here, and it is required for correctness: uvicorn runs without
    ``--proxy-headers``, so ``request.client.host`` would be nginx's own address
    and every caller would share a single bucket. Falls back to the peer address
    for direct (non-proxied) access.
    """
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return get_remote_address(request) or "anonymous"


def install_rate_limiter(app: FastAPI, settings: Settings) -> None:
    """Attach the slowapi limiter, its 429 handler, and the probe exemptions."""
    limiter = Limiter(
        key_func=rate_limit_key,
        default_limits=[f"{settings.rate_limit_per_minute}/minute"],
        # In-memory storage keeps this air-gapped and dependency-free (no Redis
        # in the compose topology). Limits are therefore per backend process.
        storage_uri="memory://",
        headers_enabled=True,
    )
    app.state.limiter = limiter

    # Never throttle the probes — slowapi keys exemptions by
    # "<module>.<function>", which is exactly what Limiter.exempt records.
    from app.api.v1.routes.health import health, ready

    limiter.exempt(health)  # type: ignore[no-untyped-call]  # slowapi is untyped
    limiter.exempt(ready)  # type: ignore[no-untyped-call]  # slowapi is untyped

    # MUST be synchronous: SlowAPIMiddleware dispatches through
    # slowapi.middleware.sync_check_limits, which silently substitutes its own
    # default handler for any coroutine handler — an async version here would be
    # discarded and callers would get slowapi's plain-text body instead of the
    # §7 envelope.
    def _handle_rate_limit(request: Request, exc: Exception) -> JSONResponse:
        rid = _request_id(request)
        logger.warning("rate_limited", path=request.url.path, request_id=rid)
        return JSONResponse(
            status_code=429,
            content=_envelope(
                "rate_limited",
                "Too many requests; slow down and retry shortly.",
                rid,
            ),
        )

    app.add_exception_handler(RateLimitExceeded, _handle_rate_limit)
    app.add_middleware(SlowAPIMiddleware)
