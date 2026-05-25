"""Backtest endpoints."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_db_session
from presentation.api_response import ok
from quant_os_infra_market.providers import ProviderFactory, ensure_providers_initialized

router = APIRouter()


class BacktestRunResponse(BaseModel):
    id: str
    strategy_id: str
    status: str
    start_date: date
    end_date: date
    benchmark_code: str | None = None
    engine: str | None = None
    annual_return: float | None = None
    sharpe_ratio: float | None = None
    max_drawdown: float | None = None
    alpha: float | None = None
    beta: float | None = None
    total_return: float | None = None
    benchmark_return: float | None = None
    excess_return: float | None = None
    information_ratio: float | None = None
    win_rate: float | None = None
    profit_loss_ratio: float | None = None
    avg_turnover: float | None = None
    calmar_ratio: float | None = None

    model_config = {"from_attributes": True}


class BacktestRunRequest(BaseModel):
    strategy_id: str
    start_date: date
    end_date: date
    benchmark_code: str = "000300.SH"
    engine: str = "internal"
    initial_capital: Decimal = Decimal("1000000")
    commission_rate: Decimal = Decimal("0.0003")
    slippage_rate: Decimal = Decimal("0.001")


class BacktestSyncRunRequest(BaseModel):
    strategy_id: str = "demo_momentum"
    start_date: date
    end_date: date
    benchmark: str = "000300.SH"
    benchmark_code: str | None = None
    initial_capital: Decimal = Decimal("1000000")
    commission_rate: Decimal = Decimal("0.0003")
    slippage_rate: Decimal = Decimal("0.001")
    mode: str = "simple"
    max_holdings: int = 5


class BacktestExecuteRequest(BaseModel):
    backtest_run_id: str


class BacktestExecuteResponse(BaseModel):
    backtest_run_id: str
    status: str
    message: str
    result: dict | None = None


class BacktestCancelRequest(BaseModel):
    backtest_run_id: str


class BacktestCancelResponse(BaseModel):
    backtest_run_id: str
    status: str
    message: str


def _run_to_api(run) -> dict:
    return {
        "id": run.id,
        "strategy_id": run.strategy_id,
        "status": run.status,
        "start_date": str(run.start_date),
        "end_date": str(run.end_date),
        "benchmark": run.benchmark_code,
        "benchmark_code": run.benchmark_code,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "total_return": run.total_return,
        "annual_return": run.annual_return,
        "sharpe_ratio": run.sharpe_ratio,
        "max_drawdown": run.max_drawdown,
    }


def _result_to_api(run) -> dict:
    return {
        "backtest_id": run.id,
        "strategy_id": run.strategy_id,
        "period": f"{run.start_date} to {run.end_date}",
        "results": {
            "total_return": run.total_return or 0,
            "annual_return": run.annual_return or 0,
            "max_drawdown": run.max_drawdown or 0,
            "sharpe_ratio": run.sharpe_ratio or 0,
            "win_rate": run.win_rate,
            "profit_loss_ratio": run.profit_loss_ratio,
            "trade_count": len(run.trade_log or []),
        },
        "benchmark_return": run.benchmark_return,
        "excess_return": run.excess_return,
        "time_series": {
            "nav_series": run.nav_series or [],
            "drawdown_series": run.drawdown_series or [],
            "monthly_returns": run.monthly_returns or [],
        },
    }


async def _ensure_strategy(db: AsyncSession, request: BacktestSyncRunRequest) -> None:
    from sqlalchemy import select
    from quant_os_infra_strategy.models.strategy_model import StrategyModel

    result = await db.execute(select(StrategyModel).where(StrategyModel.id == request.strategy_id))
    if result.scalar_one_or_none():
        return

    db.add(
        StrategyModel(
            id=request.strategy_id,
            name=request.strategy_id,
            description="Demo strategy created from API request",
            strategy_type=request.mode,
            config={"mode": request.mode},
            max_holdings=request.max_holdings,
            commission_rate=request.commission_rate,
            slippage_rate=request.slippage_rate,
            created_by="api",
        )
    )
    await db.flush()


@router.get("")
async def list_backtests_compat(
    strategy_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    from quant_os_app_backtest.services.backtest_service import BacktestService

    ensure_providers_initialized()
    service = BacktestService(session=db, provider=ProviderFactory.get())
    runs = await service.list_backtest_runs(strategy_id=strategy_id, status=status, limit=limit)
    return ok([_run_to_api(r) for r in runs])


@router.get("/runs", response_model=list[BacktestRunResponse])
async def list_backtest_runs(
    strategy_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db_session),
) -> list[BacktestRunResponse]:
    """List backtest runs with optional filters."""
    from quant_os_app_backtest.services.backtest_service import BacktestService
    
    ensure_providers_initialized()
    provider = ProviderFactory.get()
    service = BacktestService(session=db, provider=provider)
    
    runs = await service.list_backtest_runs(
        strategy_id=strategy_id,
        status=status,
    )
    
    return [BacktestRunResponse.model_validate(r) for r in runs]


@router.post("/runs", response_model=BacktestRunResponse)
async def submit_backtest_run(
    request: BacktestRunRequest,
    db: AsyncSession = Depends(get_db_session),
) -> BacktestRunResponse:
    """Create a new backtest run."""
    from quant_os_app_backtest.services.backtest_service import BacktestService
    
    ensure_providers_initialized()
    provider = ProviderFactory.get()
    service = BacktestService(session=db, provider=provider)
    
    try:
        run = await service.create_backtest_run(
            strategy_id=request.strategy_id,
            start_date=request.start_date,
            end_date=request.end_date,
            benchmark_code=request.benchmark_code,
            engine=request.engine,
            initial_capital=request.initial_capital,
            commission_rate=request.commission_rate,
            slippage_rate=request.slippage_rate,
        )
        return BacktestRunResponse.model_validate(run)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/runs/{run_id}", response_model=BacktestRunResponse)
async def get_backtest_run(
    run_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> BacktestRunResponse:
    """Get backtest run by ID."""
    from quant_os_app_backtest.services.backtest_service import BacktestService
    
    ensure_providers_initialized()
    provider = ProviderFactory.get()
    service = BacktestService(session=db, provider=provider)
    
    run = await service.get_backtest_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Backtest run {run_id} not found")
    
    return BacktestRunResponse.model_validate(run)


@router.post("/runs/{run_id}/execute", response_model=BacktestExecuteResponse)
async def execute_backtest_run(
    run_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> BacktestExecuteResponse:
    """Execute a backtest run asynchronously via Celery."""
    from quant_os_app_backtest.services.backtest_service import BacktestService
    
    ensure_providers_initialized()
    provider = ProviderFactory.get()
    service = BacktestService(session=db, provider=provider)
    
    try:
        # Verify backtest run exists and is in pending/failed status
        backtest_run = await service.get_backtest_run(run_id)
        if not backtest_run:
            raise HTTPException(
                status_code=404,
                detail=f"Backtest run {run_id} not found"
            )
        
        if backtest_run.status not in ["pending", "failed"]:
            raise HTTPException(
                status_code=400,
                detail=f"Backtest run {run_id} cannot be executed (status: {backtest_run.status})"
            )
        
        # Submit to Celery for async execution
        from workers.tasks.backtest_tasks import run_backtest_task
        task = run_backtest_task.delay(run_id)
        
        return BacktestExecuteResponse(
            backtest_run_id=run_id,
            status="submitted",
            message=f"Backtest submitted for async execution (task_id: {task.id})",
        )
    except HTTPException:
        raise
    except Exception as e:
        return BacktestExecuteResponse(
            backtest_run_id=run_id,
            status="failed",
            message=str(e),
        )


@router.post("/runs/{run_id}/cancel", response_model=BacktestCancelResponse)
async def cancel_backtest_run(
    run_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> BacktestCancelResponse:
    """Cancel a pending or running backtest."""
    from quant_os_app_backtest.services.backtest_service import BacktestService
    
    ensure_providers_initialized()
    provider = ProviderFactory.get()
    service = BacktestService(session=db, provider=provider)
    
    success = await service.cancel_backtest_run(run_id)
    
    if success:
        return BacktestCancelResponse(
            backtest_run_id=run_id,
            status="cancelled",
            message="Backtest cancelled successfully",
        )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel backtest run {run_id} (not found or not cancellable)",
        )


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str) -> dict:
    """Get Celery task status."""
    from workers.celery_app import celery_app
    
    task = celery_app.AsyncResult(task_id)
    
    response = {
        "task_id": task_id,
        "status": task.status,
        "result": None,
        "error": None,
    }
    
    if task.ready():
        if task.successful():
            response["result"] = task.result
        else:
            response["error"] = str(task.result)
    
    return response


@router.get("/runs/{run_id}/results")
async def get_backtest_results(
    run_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Get detailed backtest results including time series data."""
    from quant_os_app_backtest.services.backtest_service import BacktestService
    
    ensure_providers_initialized()
    provider = ProviderFactory.get()
    service = BacktestService(session=db, provider=provider)
    
    run = await service.get_backtest_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Backtest run {run_id} not found")
    
    if run.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Backtest run {run_id} is not completed (status: {run.status})",
        )
    
    return {
        "backtest_run_id": run_id,
        "strategy_id": run.strategy_id,
        "status": run.status,
        "start_date": str(run.start_date),
        "end_date": str(run.end_date),
        "benchmark_code": run.benchmark_code,
        "metrics": {
            "total_return": run.total_return,
            "annual_return": run.annual_return,
            "benchmark_return": run.benchmark_return,
            "excess_return": run.excess_return,
            "sharpe_ratio": run.sharpe_ratio,
            "max_drawdown": run.max_drawdown,
            "calmar_ratio": run.calmar_ratio,
            "information_ratio": run.information_ratio,
            "alpha": run.alpha,
            "beta": run.beta,
            "win_rate": run.win_rate,
            "profit_loss_ratio": run.profit_loss_ratio,
            "avg_turnover": run.avg_turnover,
        },
        "time_series": {
            "nav_series": run.nav_series,
            "drawdown_series": run.drawdown_series,
            "monthly_returns": run.monthly_returns,
            "position_history": run.position_history,
            "trade_log": run.trade_log,
        },
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }


@router.post("/run")
async def run_backtest_sync(
    request: BacktestSyncRunRequest,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Create and execute a backtest synchronously for the frontend workflow."""
    from quant_os_app_backtest.services.backtest_service import BacktestService

    await _ensure_strategy(db, request)
    ensure_providers_initialized()
    service = BacktestService(session=db, provider=ProviderFactory.get())
    run = await service.create_backtest_run(
        strategy_id=request.strategy_id,
        start_date=request.start_date,
        end_date=request.end_date,
        benchmark_code=request.benchmark_code or request.benchmark,
        initial_capital=request.initial_capital,
        commission_rate=request.commission_rate,
        slippage_rate=request.slippage_rate,
    )
    await service.execute_backtest(run.id)
    completed = await service.get_backtest_run(run.id)
    return ok(_result_to_api(completed))


@router.get("/{run_id}")
async def get_backtest_result_compat(
    run_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    from quant_os_app_backtest.services.backtest_service import BacktestService

    ensure_providers_initialized()
    service = BacktestService(session=db, provider=ProviderFactory.get())
    run = await service.get_backtest_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Backtest run {run_id} not found")
    return ok(_result_to_api(run))
