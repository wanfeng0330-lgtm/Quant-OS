"""AI Quant Research OS - API Server."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from quant_os_shared.logging.structured import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown."""
    setup_logging(log_level=app.state.settings.app.log_level)
    logger = __import__("structlog").get_logger("api")
    logger.info("Starting AI Quant Research OS API")

    # Initialize data providers (non-fatal if it fails)
    try:
        from quant_os_infra_market.providers import init_providers_from_settings
        settings = app.state.settings
        init_providers_from_settings(settings)
    except Exception as e:
        logger.warning("Failed to initialize data providers: %s", e)

    yield
    logger.info("Shutting down AI Quant Research OS API")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    from config import get_app_settings
    from presentation.router import api_router
    from middleware.error_handler import register_exception_handlers
    from middleware.correlation_id import CorrelationIdMiddleware
    from middleware.timing import TimingMiddleware

    settings = get_app_settings()

    app = FastAPI(
        title="AI Quant Research OS",
        description="AI-native quantitative research platform for A-shares",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.state.settings = settings

    # Parse CORS origins - handle both list and JSON string
    cors_origins = settings.app.cors_origins
    if isinstance(cors_origins, str):
        try:
            cors_origins = json.loads(cors_origins)
        except (json.JSONDecodeError, TypeError):
            cors_origins = [cors_origins]

    # Middleware (order matters: last added = first executed)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(TimingMiddleware)

    # Exception handlers
    register_exception_handlers(app)

    # Routers
    app.include_router(api_router)

    # Simple root health check for Railway (no DB dependency)
    @app.get("/health")
    async def root_health():
        return {"status": "ok"}

    return app


app = create_app()
