"""Market query tools for Agent - registered via ToolRegistry.

These tools query A-share market data from the database and AKShare.
Each tool manages its own DB session via get_session().
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta

from sqlalchemy import case, desc as sql_desc, func as sqlfunc, select

from .base import ToolParameter, ToolParameterType
from .registry import register_tool_function

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


async def _fetch_latest_ohlcv_stats(session) -> dict | None:
    """Fetch market overview stats for the latest trade date. Returns None if no data."""
    from quant_os_infra_market.models.ohlcv_model import OHLCVDailyModel

    ohlcv_count = (await session.execute(select(sqlfunc.count()).select_from(OHLCVDailyModel))).scalar() or 0
    if ohlcv_count == 0:
        return None

    latest_date = (await session.execute(
        select(OHLCVDailyModel.trade_date)
        .group_by(OHLCVDailyModel.trade_date)
        .order_by(sqlfunc.count().desc())
        .limit(1)
    )).scalar_one_or_none()

    if not latest_date:
        return None

    stats = (await session.execute(select(
        sqlfunc.count(),
        sqlfunc.sum(case((OHLCVDailyModel.pct_chg > 0, 1), else_=0)),
        sqlfunc.sum(case((OHLCVDailyModel.pct_chg < 0, 1), else_=0)),
        sqlfunc.sum(case((OHLCVDailyModel.pct_chg >= 9.9, 1), else_=0)),
        sqlfunc.sum(case((OHLCVDailyModel.pct_chg <= -9.9, 1), else_=0)),
        sqlfunc.sum(OHLCVDailyModel.amount),
        sqlfunc.avg(OHLCVDailyModel.pct_chg),
    ).where(OHLCVDailyModel.trade_date == latest_date))).one()

    return {
        "date": str(latest_date),
        "total": int(stats[0]),
        "up": int(stats[1] or 0),
        "down": int(stats[2] or 0),
        "limit_up": int(stats[3] or 0),
        "limit_down": int(stats[4] or 0),
        "amount_billion": round(float(stats[5] or 0) / 1e8, 2),
        "avg_pct_chg": round(float(stats[6] or 0), 2),
    }


async def _get_latest_date(session):
    """Get the trade date with most records."""
    from quant_os_infra_market.models.ohlcv_model import OHLCVDailyModel

    return (await session.execute(
        select(OHLCVDailyModel.trade_date)
        .group_by(OHLCVDailyModel.trade_date)
        .order_by(sqlfunc.count().desc())
        .limit(1)
    )).scalar_one_or_none()


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------


@register_tool_function(
    name="query_market_overview",
    description="查询A股市场整体概况：涨跌家数、涨跌停数、成交额、平均涨跌幅等",
    parameters=[],
)
async def query_market_overview() -> str:
    from quant_os_infra_market.session import get_session

    async with get_session() as session:
        stats = await _fetch_latest_ohlcv_stats(session)
        if stats is None:
            return json.dumps({"error": "无行情数据"}, ensure_ascii=False)
        return json.dumps(stats, ensure_ascii=False)


@register_tool_function(
    name="query_indices",
    description="查询主要市场指数（上证指数、深证成指、沪深300、创业板指、科创50）的最新行情",
    parameters=[],
)
async def query_indices() -> str:
    import akshare as ak

    loop = asyncio.get_event_loop()
    indices = {
        "上证指数": "sh000001",
        "深证成指": "sz399001",
        "沪深300": "sh000300",
        "创业板指": "sz399006",
        "科创50": "sh000688",
    }
    sd = (datetime.now().date() - timedelta(days=10)).strftime("%Y%m%d")
    result = {}
    for n, s in indices.items():
        try:
            df = await loop.run_in_executor(None, lambda s=s: ak.stock_zh_index_daily_em(symbol=s, start_date=sd))
            if not df.empty:
                latest = df.iloc[-1]
                prev = df.iloc[-2] if len(df) > 1 else latest
                pct = round((float(latest["close"]) - float(prev["close"])) / float(prev["close"]) * 100, 2) if float(prev["close"]) > 0 else 0
                result[n] = {"close": round(float(latest["close"]), 2), "pct_chg": pct}
        except Exception:
            pass
    return json.dumps(result, ensure_ascii=False)


@register_tool_function(
    name="query_limit_up",
    description="查询今日涨停板个股列表，含连板数、所属行业",
    parameters=[
        ToolParameter(name="limit", type=ToolParameterType.INTEGER, description="返回条数，默认30", required=False, default=30),
    ],
)
async def query_limit_up(limit: int = 30) -> str:
    import akshare as ak

    loop = asyncio.get_event_loop()
    zt_df = await loop.run_in_executor(None, lambda: ak.stock_zt_pool_em(date=datetime.now().strftime("%Y%m%d")))
    if zt_df.empty:
        return json.dumps({"error": "今日无涨停数据"}, ensure_ascii=False)
    cols = list(zt_df.columns)
    records = []
    for _, row in zt_df.head(limit).iterrows():
        records.append({
            "name": str(row.iloc[2]) if len(cols) > 2 else "",
            "code": str(row.iloc[1]) if len(cols) > 1 else "",
            "pct_chg": round(float(row.iloc[3]), 2) if len(cols) > 3 else 0,
            "consecutive": int(row.iloc[14]) if len(cols) > 14 else 1,
            "industry": str(row.iloc[15]) if len(cols) > 15 else "",
        })
    return json.dumps(records, ensure_ascii=False)


@register_tool_function(
    name="query_limit_down",
    description="查询今日跌停板个股列表",
    parameters=[
        ToolParameter(name="limit", type=ToolParameterType.INTEGER, description="返回条数，默认20", required=False, default=20),
    ],
)
async def query_limit_down(limit: int = 20) -> str:
    from quant_os_infra_market.session import get_session
    from quant_os_infra_market.models.ohlcv_model import OHLCVDailyModel
    from quant_os_infra_market.models.stock_model import StockModel

    async with get_session() as session:
        latest_date = await _get_latest_date(session)
        if not latest_date:
            return json.dumps({"error": "无行情数据"}, ensure_ascii=False)
        rows = (await session.execute(
            select(StockModel.name, StockModel.ts_code, StockModel.industry, OHLCVDailyModel.close, OHLCVDailyModel.pct_chg, OHLCVDailyModel.amount)
            .join(OHLCVDailyModel, StockModel.ts_code == OHLCVDailyModel.ts_code)
            .where(OHLCVDailyModel.trade_date == latest_date)
            .where(OHLCVDailyModel.pct_chg <= -9.9)
            .order_by(OHLCVDailyModel.pct_chg)
            .limit(limit)
        )).all()
        return json.dumps([{
            "name": r[0], "ts_code": r[1], "industry": r[2],
            "close": float(r[3]), "pct_chg": float(r[4]),
            "amount_billion": round(float(r[5] or 0) / 1e8, 2),
        } for r in rows], ensure_ascii=False)


@register_tool_function(
    name="query_sector",
    description="查询指定板块/行业的个股行情。可按行业名称筛选，返回该行业股票的涨跌幅、成交额等",
    parameters=[
        ToolParameter(name="sector", type=ToolParameterType.STRING, description="行业名称，如'通信'、'电子'、'银行'、'医药'等", required=True),
        ToolParameter(name="limit", type=ToolParameterType.INTEGER, description="返回条数，默认20", required=False, default=20),
    ],
)
async def query_sector(sector: str, limit: int = 20) -> str:
    from quant_os_infra_market.session import get_session
    from quant_os_infra_market.models.ohlcv_model import OHLCVDailyModel
    from quant_os_infra_market.models.stock_model import StockModel

    async with get_session() as session:
        ohlcv_count = (await session.execute(select(sqlfunc.count()).select_from(OHLCVDailyModel))).scalar() or 0
        if ohlcv_count == 0:
            return json.dumps({"error": "无行情数据"}, ensure_ascii=False)
        latest_date = await _get_latest_date(session)
        rows = (await session.execute(
            select(StockModel.name, StockModel.ts_code, OHLCVDailyModel.close, OHLCVDailyModel.pct_chg, OHLCVDailyModel.amount, OHLCVDailyModel.volume)
            .join(OHLCVDailyModel, StockModel.ts_code == OHLCVDailyModel.ts_code)
            .where(OHLCVDailyModel.trade_date == latest_date)
            .where(StockModel.industry.ilike(f"%{sector}%"))
            .order_by(sql_desc(OHLCVDailyModel.pct_chg))
            .limit(limit)
        )).all()
        if not rows:
            return json.dumps({"error": f"未找到'{sector}'相关板块数据", "hint": "请检查行业名称，如通信、电子、银行、医药等"}, ensure_ascii=False)
        return json.dumps({
            "sector": sector, "date": str(latest_date), "count": len(rows),
            "stocks": [{"name": r[0], "ts_code": r[1], "close": float(r[2]), "pct_chg": float(r[3]), "amount_billion": round(float(r[4] or 0) / 1e8, 2)} for r in rows],
        }, ensure_ascii=False)


@register_tool_function(
    name="query_sector_ranking",
    description="查询所有行业板块的涨跌幅排行，返回每个行业的平均涨跌幅、涨跌家数、成交额。用于回答'哪个板块涨得最猛'、'板块排行'等问题",
    parameters=[
        ToolParameter(name="limit", type=ToolParameterType.INTEGER, description="返回条数，默认30", required=False, default=30),
        ToolParameter(name="sort_by", type=ToolParameterType.STRING, description="排序方式，默认gainers", required=False, enum=["gainers", "losers"]),
    ],
)
async def query_sector_ranking(sort_by: str = "gainers", limit: int = 30) -> str:
    from quant_os_infra_market.session import get_session
    from quant_os_infra_market.models.ohlcv_model import OHLCVDailyModel
    from quant_os_infra_market.models.stock_model import StockModel

    async with get_session() as session:
        ohlcv_count = (await session.execute(select(sqlfunc.count()).select_from(OHLCVDailyModel))).scalar() or 0
        if ohlcv_count == 0:
            return json.dumps({"error": "无行情数据"}, ensure_ascii=False)
        latest_date = await _get_latest_date(session)
        order = sql_desc(sqlfunc.avg(OHLCVDailyModel.pct_chg)) if sort_by == "gainers" else sqlfunc.avg(OHLCVDailyModel.pct_chg)
        rows = (await session.execute(
            select(
                StockModel.industry,
                sqlfunc.count().label("count"),
                sqlfunc.avg(OHLCVDailyModel.pct_chg).label("avg_pct_chg"),
                sqlfunc.sum(case((OHLCVDailyModel.pct_chg > 0, 1), else_=0)).label("up_count"),
                sqlfunc.sum(case((OHLCVDailyModel.pct_chg < 0, 1), else_=0)).label("down_count"),
                sqlfunc.sum(OHLCVDailyModel.amount).label("total_amount"),
            )
            .join(OHLCVDailyModel, StockModel.ts_code == OHLCVDailyModel.ts_code)
            .where(OHLCVDailyModel.trade_date == latest_date)
            .where(StockModel.industry.isnot(None))
            .group_by(StockModel.industry)
            .order_by(order)
            .limit(limit)
        )).all()
        return json.dumps([{
            "industry": r[0], "count": int(r[1]),
            "avg_pct_chg": round(float(r[2] or 0), 2),
            "up": int(r[3] or 0), "down": int(r[4] or 0),
            "amount_billion": round(float(r[5] or 0) / 1e8, 2),
        } for r in rows], ensure_ascii=False)


@register_tool_function(
    name="query_top_stocks",
    description="查询涨幅榜、跌幅榜或成交额排行",
    parameters=[
        ToolParameter(name="sort_by", type=ToolParameterType.STRING, description="排序方式：gainers=涨幅榜, losers=跌幅榜, volume=成交额榜", required=True, enum=["gainers", "losers", "volume"]),
        ToolParameter(name="limit", type=ToolParameterType.INTEGER, description="返回条数，默认15", required=False, default=15),
    ],
)
async def query_top_stocks(sort_by: str, limit: int = 15) -> str:
    from quant_os_infra_market.session import get_session
    from quant_os_infra_market.models.ohlcv_model import OHLCVDailyModel
    from quant_os_infra_market.models.stock_model import StockModel

    async with get_session() as session:
        latest_date = await _get_latest_date(session)
        if not latest_date:
            return json.dumps({"error": "无行情数据"}, ensure_ascii=False)
        q = select(StockModel.name, OHLCVDailyModel.ts_code, OHLCVDailyModel.close, OHLCVDailyModel.pct_chg, OHLCVDailyModel.amount).join(OHLCVDailyModel, StockModel.ts_code == OHLCVDailyModel.ts_code).where(OHLCVDailyModel.trade_date == latest_date)
        if sort_by == "gainers":
            q = q.order_by(sql_desc(OHLCVDailyModel.pct_chg))
        elif sort_by == "losers":
            q = q.order_by(OHLCVDailyModel.pct_chg)
        else:
            q = q.order_by(sql_desc(OHLCVDailyModel.amount))
        rows = (await session.execute(q.limit(limit))).all()
        return json.dumps([{"name": r[0], "ts_code": r[1], "close": float(r[2]), "pct_chg": float(r[3]), "amount_billion": round(float(r[4] or 0) / 1e8, 2)} for r in rows], ensure_ascii=False)


@register_tool_function(
    name="query_dragon_tiger",
    description="查询龙虎榜数据，含买卖金额、净额、上榜原因",
    parameters=[
        ToolParameter(name="limit", type=ToolParameterType.INTEGER, description="返回条数，默认20", required=False, default=20),
    ],
)
async def query_dragon_tiger(limit: int = 20) -> str:
    from quant_os_infra_market.session import get_session
    from quant_os_infra_market.models.dragon_tiger_model import DragonTigerModel

    async with get_session() as session:
        rows = (await session.execute(
            select(DragonTigerModel).order_by(DragonTigerModel.trade_date.desc()).limit(limit)
        )).scalars().all()
        return json.dumps([{
            "name": getattr(r, "name", None) or r.ts_code, "ts_code": r.ts_code,
            "reason": r.reason, "buy_amount": float(r.buy_amount or 0),
            "sell_amount": float(r.sell_amount or 0), "net_amount": float(r.net_amount or 0),
            "date": str(r.trade_date),
        } for r in rows], ensure_ascii=False)


@register_tool_function(
    name="query_stock",
    description="查询单只股票的最新行情数据，含行业、价格、涨跌幅、成交量",
    parameters=[
        ToolParameter(name="ts_code", type=ToolParameterType.STRING, description="股票代码，如'000001.SZ'、'600519.SH'", required=True),
    ],
)
async def query_stock(ts_code: str) -> str:
    from quant_os_infra_market.session import get_session
    from quant_os_infra_market.models.ohlcv_model import OHLCVDailyModel
    from quant_os_infra_market.models.stock_model import StockModel

    async with get_session() as session:
        stock = (await session.execute(select(StockModel).where(StockModel.ts_code == ts_code))).scalar_one_or_none()
        if not stock:
            return json.dumps({"error": f"股票{ts_code}不存在"}, ensure_ascii=False)
        latest = (await session.execute(select(OHLCVDailyModel).where(OHLCVDailyModel.ts_code == ts_code).order_by(OHLCVDailyModel.trade_date.desc()).limit(1))).scalar_one_or_none()
        if not latest:
            return json.dumps({"name": stock.name, "ts_code": ts_code, "error": "无行情数据"}, ensure_ascii=False)
        return json.dumps({
            "name": stock.name, "ts_code": ts_code, "industry": stock.industry,
            "close": float(latest.close), "pct_chg": float(latest.pct_chg),
            "volume": float(latest.volume), "amount": float(latest.amount or 0),
            "date": str(latest.trade_date),
        }, ensure_ascii=False)


@register_tool_function(
    name="query_stock_history",
    description="查询单只股票最近N天的历史行情数据，含每日OHLCV和涨跌幅",
    parameters=[
        ToolParameter(name="ts_code", type=ToolParameterType.STRING, description="股票代码，如'000001.SZ'", required=True),
        ToolParameter(name="days", type=ToolParameterType.INTEGER, description="天数，默认20", required=False, default=20),
    ],
)
async def query_stock_history(ts_code: str, days: int = 20) -> str:
    from quant_os_infra_market.session import get_session
    from quant_os_infra_market.models.ohlcv_model import OHLCVDailyModel

    async with get_session() as session:
        rows = (await session.execute(
            select(OHLCVDailyModel).where(OHLCVDailyModel.ts_code == ts_code)
            .order_by(OHLCVDailyModel.trade_date.desc()).limit(days)
        )).scalars().all()
        if not rows:
            return json.dumps({"error": f"股票{ts_code}无历史数据"}, ensure_ascii=False)
        return json.dumps([{
            "date": str(r.trade_date), "open": float(r.open), "high": float(r.high),
            "low": float(r.low), "close": float(r.close), "pct_chg": float(r.pct_chg),
            "volume": float(r.volume), "amount": float(r.amount or 0),
        } for r in rows], ensure_ascii=False)


@register_tool_function(
    name="search_stocks_by_name",
    description="按股票名称模糊搜索，返回匹配的股票列表（名称、代码、行业）",
    parameters=[
        ToolParameter(name="keyword", type=ToolParameterType.STRING, description="搜索关键词，如'茅台'、'宁德'", required=True),
    ],
)
async def search_stocks_by_name(keyword: str) -> str:
    from quant_os_infra_market.session import get_session
    from quant_os_infra_market.models.stock_model import StockModel

    async with get_session() as session:
        rows = (await session.execute(
            select(StockModel).where(StockModel.name.ilike(f"%{keyword}%")).limit(10)
        )).scalars().all()
        return json.dumps([{
            "name": s.name, "ts_code": s.ts_code, "industry": s.industry,
        } for s in rows], ensure_ascii=False)


@register_tool_function(
    name="query_market_distribution",
    description="查询市场涨跌幅分布统计：多少股票涨超5%、跌超5%、涨停、跌停等分布情况。用于分析市场整体强弱",
    parameters=[],
)
async def query_market_distribution() -> str:
    from quant_os_infra_market.session import get_session
    from quant_os_infra_market.models.ohlcv_model import OHLCVDailyModel

    async with get_session() as session:
        latest_date = await _get_latest_date(session)
        if not latest_date:
            return json.dumps({"error": "无行情数据"}, ensure_ascii=False)
        dist = (await session.execute(select(
            sqlfunc.count(),
            sqlfunc.sum(case((OHLCVDailyModel.pct_chg >= 9.9, 1), else_=0)),
            sqlfunc.sum(case((OHLCVDailyModel.pct_chg >= 5, 1), else_=0)),
            sqlfunc.sum(case((OHLCVDailyModel.pct_chg >= 0, 1), else_=0)),
            sqlfunc.sum(case((OHLCVDailyModel.pct_chg <= -5, 1), else_=0)),
            sqlfunc.sum(case((OHLCVDailyModel.pct_chg <= -9.9, 1), else_=0)),
            sqlfunc.sum(case((OHLCVDailyModel.pct_chg.between(-1, 1), 1), else_=0)),
        ).where(OHLCVDailyModel.trade_date == latest_date))).one()
        return json.dumps({
            "date": str(latest_date), "total": int(dist[0]),
            "limit_up": int(dist[1] or 0), "up_5pct": int(dist[2] or 0),
            "up": int(dist[3] or 0), "down_5pct": int(dist[4] or 0),
            "limit_down": int(dist[5] or 0), "flat_range": int(dist[6] or 0),
        }, ensure_ascii=False)


@register_tool_function(
    name="query_consecutive_limit_up",
    description="查询连板股列表（连续涨停2天以上的股票），用于分析市场情绪和龙头股",
    parameters=[
        ToolParameter(name="min_days", type=ToolParameterType.INTEGER, description="最少连板天数，默认2", required=False, default=2),
    ],
)
async def query_consecutive_limit_up(min_days: int = 2) -> str:
    import akshare as ak

    loop = asyncio.get_event_loop()
    zt_df = await loop.run_in_executor(None, lambda: ak.stock_zt_pool_em(date=datetime.now().strftime("%Y%m%d")))
    if zt_df.empty:
        return json.dumps({"error": "今日无涨停数据"}, ensure_ascii=False)
    cols = list(zt_df.columns)
    records = []
    for _, row in zt_df.iterrows():
        consecutive = int(row.iloc[14]) if len(cols) > 14 else 1
        if consecutive >= min_days:
            records.append({
                "name": str(row.iloc[2]) if len(cols) > 2 else "",
                "code": str(row.iloc[1]) if len(cols) > 1 else "",
                "pct_chg": round(float(row.iloc[3]), 2) if len(cols) > 3 else 0,
                "consecutive": consecutive,
                "industry": str(row.iloc[15]) if len(cols) > 15 else "",
            })
    records.sort(key=lambda x: x["consecutive"], reverse=True)
    return json.dumps(records, ensure_ascii=False)


@register_tool_function(
    name="query_volume_leaders",
    description="查询换手率排行，高换手率代表资金活跃度高",
    parameters=[
        ToolParameter(name="limit", type=ToolParameterType.INTEGER, description="返回条数，默认20", required=False, default=20),
    ],
)
async def query_volume_leaders(limit: int = 20) -> str:
    from quant_os_infra_market.session import get_session
    from quant_os_infra_market.models.ohlcv_model import OHLCVDailyModel
    from quant_os_infra_market.models.stock_model import StockModel

    async with get_session() as session:
        latest_date = await _get_latest_date(session)
        if not latest_date:
            return json.dumps({"error": "无行情数据"}, ensure_ascii=False)
        rows = (await session.execute(
            select(StockModel.name, StockModel.ts_code, StockModel.industry, OHLCVDailyModel.close, OHLCVDailyModel.pct_chg, OHLCVDailyModel.volume, OHLCVDailyModel.amount)
            .join(OHLCVDailyModel, StockModel.ts_code == OHLCVDailyModel.ts_code)
            .where(OHLCVDailyModel.trade_date == latest_date)
            .where(OHLCVDailyModel.volume > 0)
            .order_by(sql_desc(OHLCVDailyModel.volume))
            .limit(limit)
        )).all()
        return json.dumps([{
            "name": r[0], "ts_code": r[1], "industry": r[2],
            "close": float(r[3]), "pct_chg": float(r[4]),
            "volume": float(r[5]), "amount_billion": round(float(r[6] or 0) / 1e8, 2),
        } for r in rows], ensure_ascii=False)
