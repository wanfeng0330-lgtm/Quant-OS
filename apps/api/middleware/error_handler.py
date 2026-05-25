"""Global exception handler middleware."""

from __future__ import annotations

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from quant_os_shared.errors import (
    QuantOSError, DataNotFoundError, FactorNotFoundError,
    BacktestConfigError, LLMRateLimitError,
)

logger = structlog.get_logger("api.errors")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(QuantOSError)
    async def quant_os_error_handler(request: Request, exc: QuantOSError) -> JSONResponse:
        logger.error("QuantOS error", error=exc.message, code=exc.code)
        status_code = 500
        if isinstance(exc, (DataNotFoundError, FactorNotFoundError)):
            status_code = 404
        elif isinstance(exc, BacktestConfigError):
            status_code = 400
        elif isinstance(exc, LLMRateLimitError):
            status_code = 429

        return JSONResponse(
            status_code=status_code,
            content={"error": exc.code, "message": exc.message, "details": exc.details},
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled error", error=str(exc), exc_info=True)
        # In development, include more error details
        import traceback
        from config import get_app_settings
        settings = get_app_settings()
        content = {"error": "InternalError", "message": "An unexpected error occurred"}
        if settings.app.debug:
            content["detail"] = str(exc)
            content["type"] = type(exc).__name__
            content["traceback"] = traceback.format_exc()
        return JSONResponse(
            status_code=500,
            content=content,
        )
