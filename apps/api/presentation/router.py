"""Master API router."""

from fastapi import APIRouter

from presentation.v1 import market, factors, backtest, agents, system, workflows, reports, sentiment, research
from presentation.ws import workflow_stream, event_stream

api_router = APIRouter()

api_router.include_router(system.router, prefix="/api/v1/system", tags=["System"])
api_router.include_router(market.router, prefix="/api/v1/market", tags=["Market Data"])
api_router.include_router(factors.router, prefix="/api/v1/factors", tags=["Factor Engine"])
api_router.include_router(backtest.router, prefix="/api/v1/backtest", tags=["Backtest"])
api_router.include_router(agents.router, prefix="/api/v1/agents", tags=["AI Agents"])
api_router.include_router(workflows.router, prefix="/api/v1/workflows", tags=["Workflows"])
api_router.include_router(reports.router, prefix="/api/v1/reports", tags=["Research Reports"])
api_router.include_router(sentiment.router, prefix="/api/v1/sentiment", tags=["Market Sentiment"])
api_router.include_router(research.router, prefix="/api/v1/research", tags=["AI Research"])

# WebSocket routes
api_router.include_router(workflow_stream.router, tags=["WebSocket"])
api_router.include_router(event_stream.router, tags=["WebSocket"])
