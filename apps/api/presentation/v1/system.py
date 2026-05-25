"""System endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from dependencies import get_settings_cached
from quant_os_shared.config.settings import Settings

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str


class ServiceStatus(BaseModel):
    service: str
    status: str
    details: str = ""


class DetailedHealthResponse(BaseModel):
    status: str
    services: list[ServiceStatus]


@router.get("/health", response_model=HealthResponse)
async def health_check(settings: Settings = Depends(get_settings_cached)) -> HealthResponse:
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        environment=settings.app.env,
    )


@router.get("/health/detailed", response_model=DetailedHealthResponse)
async def detailed_health_check(settings: Settings = Depends(get_settings_cached)) -> DetailedHealthResponse:
    services: list[ServiceStatus] = []

    # Check PostgreSQL
    try:
        from dependencies import get_engine
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        services.append(ServiceStatus(service="postgresql", status="healthy"))
    except Exception as exc:
        services.append(ServiceStatus(service="postgresql", status="unhealthy", details=str(exc)))

    # Check Redis
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.redis.url)
        await r.ping()
        await r.aclose()
        services.append(ServiceStatus(service="redis", status="healthy"))
    except Exception as exc:
        services.append(ServiceStatus(service="redis", status="unhealthy", details=str(exc)))

    # Check Qdrant
    try:
        from qdrant_client import AsyncQdrantClient
        client = AsyncQdrantClient(url=settings.qdrant.url)
        await client.get_collections()
        await client.close()
        services.append(ServiceStatus(service="qdrant", status="healthy"))
    except Exception as exc:
        services.append(ServiceStatus(service="qdrant", status="unhealthy", details=str(exc)))

    overall = "healthy" if all(s.status == "healthy" for s in services) else "degraded"

    return DetailedHealthResponse(status=overall, services=services)
