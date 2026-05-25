"""A-share market sentiment endpoints - uses real database data."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_db_session
from presentation.api_response import ok

router = APIRouter()


@router.get("/overview")
async def get_sentiment_overview(db: AsyncSession = Depends(get_db_session)) -> dict:
    """Get market sentiment overview from real data."""
    from quant_os_infra_market.models.stock_model import StockModel

    # Get real stock counts
    total_result = await db.execute(select(func.count()).select_from(StockModel))
    total_stocks = total_result.scalar() or 0

    st_result = await db.execute(
        select(func.count()).select_from(StockModel).where(StockModel.is_st == True)
    )
    st_count = st_result.scalar() or 0

    return ok({
        "date": datetime.now().strftime("%Y-%m-%d"),
        "total_stocks": total_stocks,
        "st_count": st_count,
        "message": "情绪数据需要同步涨跌停数据后才能提供完整分析",
        "data_source": "database",
    })


@router.get("/northbound")
async def get_northbound_flow(db: AsyncSession = Depends(get_db_session)) -> dict:
    """Get northbound capital flow data from database."""
    try:
        from quant_os_infra_market.models.northbound_model import NorthboundFlowModel
        result = await db.execute(select(func.count()).select_from(NorthboundFlowModel))
        count = result.scalar() or 0

        if count > 0:
            latest = await db.execute(
                select(NorthboundFlowModel).order_by(NorthboundFlowModel.trade_date.desc()).limit(30)
            )
            flows = [
                {
                    "date": str(r.trade_date),
                    "net_flow_billion": float(r.net_buy_amount or 0) / 1e8,
                }
                for r in latest.scalars()
            ]
            return ok({
                "records": count,
                "flows": flows,
                "data_source": "database",
            })
    except Exception:
        pass

    return ok({
        "records": 0,
        "message": "北向资金数据未同步，请先通过数据同步功能获取数据",
        "data_source": "none",
    })


@router.get("/dragon-tiger")
async def get_dragon_tiger(db: AsyncSession = Depends(get_db_session)) -> dict:
    """Get dragon-tiger list data from database."""
    try:
        from quant_os_infra_market.models.dragon_tiger_model import DragonTigerModel
        result = await db.execute(select(func.count()).select_from(DragonTigerModel))
        count = result.scalar() or 0

        if count > 0:
            latest = await db.execute(
                select(DragonTigerModel).order_by(DragonTigerModel.trade_date.desc()).limit(10)
            )
            entries = [
                {
                    "ts_code": r.ts_code,
                    "name": r.name,
                    "reason": r.reason,
                    "date": str(r.trade_date),
                }
                for r in latest.scalars()
            ]
            return ok({
                "date": datetime.now().strftime("%Y-%m-%d"),
                "entries": entries,
                "data_source": "database",
            })
    except Exception:
        pass

    return ok({
        "date": datetime.now().strftime("%Y-%m-%d"),
        "entries": [],
        "message": "龙虎榜数据未同步，请先通过数据同步功能获取数据",
        "data_source": "none",
    })


@router.get("/industry-rotation")
async def get_industry_rotation(db: AsyncSession = Depends(get_db_session)) -> dict:
    """Get industry rotation from real stock data."""
    from quant_os_infra_market.models.stock_model import StockModel

    # Get industry distribution from real data
    result = await db.execute(
        select(StockModel.industry, func.count().label("count"))
        .where(StockModel.industry.isnot(None))
        .group_by(StockModel.industry)
        .order_by(func.count().desc())
        .limit(20)
    )
    industries = [{"name": r[0], "stock_count": r[1]} for r in result.all()]

    return ok({
        "date": datetime.now().strftime("%Y-%m-%d"),
        "industries": industries,
        "message": "行业轮动分析需要涨跌幅数据支持",
        "data_source": "database",
    })


@router.get("/limit-stats")
async def get_limit_stats() -> dict:
    """Get limit up/down statistics."""
    return ok({
        "date": datetime.now().strftime("%Y-%m-%d"),
        "limit_up_count": 0,
        "limit_down_count": 0,
        "limit_up_stocks": [],
        "limit_down_stocks": [],
        "message": "涨跌停数据需要实时行情数据支持，请先同步数据",
        "data_source": "none",
    })
