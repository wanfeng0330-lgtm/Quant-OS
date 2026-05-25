"""Request timing middleware."""

from __future__ import annotations

import time

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger("api.timing")


class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        response.headers["X-Process-Time-Ms"] = f"{duration_ms:.2f}"

        if duration_ms > 1000:
            logger.warning(
                "Slow request",
                method=request.method,
                path=request.url.path,
                duration_ms=round(duration_ms, 2),
            )

        return response
