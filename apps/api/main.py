"""AI Quant Research OS - API Server."""

from __future__ import annotations

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

    # Initialize data providers
    from quant_os_infra_market.providers import init_providers_from_settings
    settings = app.state.settings
    init_providers_from_settings(settings)

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

    # Middleware (order matters: last added = first executed)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.app.cors_origins,
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

    return app


app = create_app()
