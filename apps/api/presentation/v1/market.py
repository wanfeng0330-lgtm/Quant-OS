"""Market data endpoints."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_db_session
from presentation.api_response import ok

router = APIRouter()


class StockResponse(BaseModel):
    ts_code: str
    symbol: str
    name: str
    exchange: str
    board: str
    industry: str | None = None
    is_st: bool = False
    is_hs: bool = False
    list_date: str | None = None
    total_share: float | None = None
    float_share: float | None = None
    status: str = "active"

    model_config = {"from_attributes": True}


class OHLCVResponse(BaseModel):
    ts_code: str
    trade_date: str
    open: float
    high: float
    low: float
    close: float
    pre_close: float | None = None
    pct_chg: float | None = None
    volume: float
    amount: float | None = None
    is_limit_up: bool | None = None
    is_limit_down: bool | None = None


class PaginatedResponse(BaseModel):
    items: list[dict]
    total: int
    page: int
    size: int


class SyncRequest(BaseModel):
    source: str = "akshare"
    data_type: str = "stock_list"
    ts_code: str | None = None
    trade_date: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    year: int | None = None


class SyncResponse(BaseModel):
    job_id: str
    status: str
    message: str
    details: dict | None = None


# --- Stock Endpoints ---


def _stock_record(row: dict) -> dict:
    list_date = row.get("list_date")
    return {
        "ts_code": row.get("ts_code"),
        "symbol": row.get("symbol"),
        "name": row.get("name"),
        "exchange": row.get("exchange"),
        "board": row.get("board"),
        "industry": row.get("industry"),
        "is_st": bool(row.get("is_st", False)),
        "is_hs": bool(row.get("is_hs", False)),
        "list_date": str(list_date) if list_date else None,
        "total_share": row.get("total_share"),
        "float_share": row.get("float_share"),
        "status": row.get("status", "active"),
    }


@router.get("/stocks")
async def list_stocks(
    exchange: Optional[str] = Query(None),
    board: Optional[str] = Query(None),
    is_st: Optional[bool] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    from quant_os_app_market.services.stock_query import StockQueryService

    svc = StockQueryService(session=db)
    result = await svc.list_stocks(
        exchange=exchange, board=board, is_st=is_st, status=status, page=page, size=size
    )
    return ok(PaginatedResponse(**result).model_dump())


@router.get("/stocks/search")
async def search_stocks(
    keyword: str = Query("", min_length=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    from quant_os_app_market.services.stock_query import StockQueryService

    svc = StockQueryService(session=db)
    stocks = await svc.search_stocks(keyword, limit) if keyword else []
    return ok(stocks)


@router.get("/stocks/{ts_code}")
async def get_stock(
    ts_code: str,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    from quant_os_app_market.services.stock_query import StockQueryService

    svc = StockQueryService(session=db)
    stock = await svc.get_stock(ts_code)
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {ts_code} not found")
    return ok(StockResponse(**stock).model_dump())


# --- OHLCV Endpoints ---


@router.get("/stocks/{ts_code}/ohlcv")
async def get_stock_ohlcv(
    ts_code: str,
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    adjust: str = Query("", description="Price adjustment: '' raw, 'qfq' forward, 'hfq' backward"),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    from datetime import datetime as dt
    from quant_os_app_market.services.ohlcv_query import OHLCVQueryService

    svc = OHLCVQueryService(session=db)
    sd = dt.strptime(start_date, "%Y-%m-%d").date() if start_date else None
    ed = dt.strptime(end_date, "%Y-%m-%d").date() if end_date else None
    bars = await svc.get_daily_bars(ts_code, sd, ed, adjust)

    # Auto-sync from baostock if no data
    if not bars:
        try:
            import asyncio
            from services.data_sync import sync_stock_ohlcv
            from quant_os_infra_market.models.ohlcv_model import OHLCVDailyModel

            rows = await asyncio.to_thread(sync_stock_ohlcv, ts_code)
            if rows:
                for r in rows:
                    db.add(OHLCVDailyModel(
                        ts_code=r["ts_code"],
                        trade_date=date.fromisoformat(r["trade_date"]),
                        open=r["open"], high=r["high"],
                        low=r["low"], close=r["close"],
                        volume=r["volume"], amount=r["amount"],
                    ))
                await db.flush()
                bars = await svc.get_daily_bars(ts_code, sd, ed, adjust)
        except Exception:
            pass

    return ok([OHLCVResponse(**b).model_dump() for b in bars])


# --- Calendar Endpoints ---


@router.get("/calendar")
async def get_trading_calendar(
    year: int = Query(..., ge=2000, le=2100),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    from sqlalchemy import select
    from quant_os_infra_market.models import TradingCalendarModel

    result = await db.execute(
        select(TradingCalendarModel)
        .where(TradingCalendarModel.cal_date >= f"{year}-01-01")
        .where(TradingCalendarModel.cal_date <= f"{year}-12-31")
        .order_by(TradingCalendarModel.cal_date)
    )
    days = result.scalars().all()
    calendar = [{"date": str(d.cal_date), "is_open": d.is_open} for d in days]
    return ok(calendar)


# --- Sync Endpoints ---


@router.post("/sync", response_model=SyncResponse)
async def trigger_data_sync(
    request: SyncRequest,
    db: AsyncSession = Depends(get_db_session),
) -> SyncResponse:
    from datetime import datetime as dt
    from quant_os_infra_market.providers import ProviderFactory
    from quant_os_app_market.services.data_ingestion import DataIngestionService

    try:
        provider = ProviderFactory.get(request.source)
    except (ValueError, StopIteration):
        raise HTTPException(status_code=400, detail=f"Unknown data source: {request.source}")

    svc = DataIngestionService(session=db, provider=provider)

    try:
        if request.data_type == "stock_list":
            details = await svc.sync_stock_list()
        elif request.data_type == "ohlcv_daily":
            ts_code = request.ts_code
            sd = dt.strptime(request.start_date, "%Y-%m-%d").date() if request.start_date else None
            ed = dt.strptime(request.end_date, "%Y-%m-%d").date() if request.end_date else None
            td = dt.strptime(request.trade_date, "%Y-%m-%d").date() if request.trade_date else None
            if td:
                details = await svc.sync_ohlcv_all_stocks(td)
            else:
                details = await svc.sync_ohlcv_daily(ts_code=ts_code, start_date=sd, end_date=ed)
        elif request.data_type == "calendar":
            details = await svc.sync_trading_calendar(year=request.year)
        elif request.data_type == "northbound":
            details = await svc.sync_northbound_flow(ts_code=request.ts_code)
        elif request.data_type == "dragon_tiger":
            details = await svc.sync_dragon_tiger()
        elif request.data_type == "sector":
            details = await svc.sync_sector_classification()
        else:
            raise HTTPException(status_code=400, detail=f"Unknown data_type: {request.data_type}")

        return SyncResponse(
            job_id=str(uuid.uuid4()),
            status="completed",
            message=f"Sync {request.data_type} completed",
            details=details,
        )
    except Exception as exc:
        return SyncResponse(
            job_id=str(uuid.uuid4()),
            status="failed",
            message=str(exc),
        )


# --- Data Source Management ---


@router.get("/providers")
async def list_providers() -> dict:
    from quant_os_infra_market.providers import ProviderFactory

    return ok({
        "providers": ProviderFactory.list_providers(),
        "primary": ProviderFactory._primary,
        "fallback": ProviderFactory._fallback,
    })


@router.post("/sync/batch")
async def batch_sync_ohlcv(
    limit: int = Query(200, ge=1, le=2000),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Batch sync OHLCV data for stocks that don't have it yet."""
    from sqlalchemy import select
    from quant_os_infra_market.models import StockModel
    from quant_os_infra_market.models.ohlcv_model import OHLCVDailyModel

    # Find stocks without data
    subq = select(OHLCVDailyModel.ts_code).distinct()
    result = await db.execute(
        select(StockModel.ts_code)
        .where(StockModel.ts_code.notin_(subq))
        .limit(limit)
    )
    ts_codes = [r[0] for r in result.all()]

    if not ts_codes:
        return ok({"synced": 0, "message": "All stocks already have data"})

    import asyncio
    from services.data_sync import batch_sync_stocks

    summary = await asyncio.to_thread(batch_sync_stocks, ts_codes)
    return ok(summary)
