"""Data synchronization endpoints - pre-fetch all market data to database."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, date

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_db_session
from presentation.api_response import ok

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory sync state
_sync_state = {
    "running": False,
    "last_run": None,
    "last_duration_seconds": None,
    "last_result": None,
    "error": None,
}


@router.get("/status")
async def get_sync_status(db: AsyncSession = Depends(get_db_session)) -> dict:
    """Get data sync status and record counts."""
    from quant_os_infra_market.models.stock_model import StockModel
    from quant_os_infra_market.models.northbound_model import NorthboundFlowModel
    from quant_os_infra_market.models.dragon_tiger_model import DragonTigerModel
    from quant_os_infra_market.models.ohlcv_model import OHLCVDailyModel

    stock_count = (await db.execute(select(func.count()).select_from(StockModel))).scalar() or 0
    nb_count = (await db.execute(select(func.count()).select_from(NorthboundFlowModel))).scalar() or 0
    dt_count = (await db.execute(select(func.count()).select_from(DragonTigerModel))).scalar() or 0
    ohlcv_count = (await db.execute(select(func.count()).select_from(OHLCVDailyModel))).scalar() or 0

    # Get latest dates
    latest_nb = (await db.execute(
        select(func.max(NorthboundFlowModel.trade_date))
    )).scalar_one_or_none()
    latest_dt = (await db.execute(
        select(func.max(DragonTigerModel.trade_date))
    )).scalar_one_or_none()
    latest_ohlcv = (await db.execute(
        select(func.max(OHLCVDailyModel.trade_date))
    )).scalar_one_or_none()

    return ok({
        "sync_running": _sync_state["running"],
        "last_sync_time": _sync_state["last_run"],
        "last_sync_duration_seconds": _sync_state["last_duration_seconds"],
        "last_sync_result": _sync_state["last_result"],
        "last_sync_error": _sync_state["error"],
        "data": {
            "stocks": {"count": stock_count},
            "northbound": {"count": nb_count, "latest_date": str(latest_nb) if latest_nb else None},
            "dragon_tiger": {"count": dt_count, "latest_date": str(latest_dt) if latest_dt else None},
            "ohlcv": {"count": ohlcv_count, "latest_date": str(latest_ohlcv) if latest_ohlcv else None},
        },
    })


@router.post("/all")
async def trigger_full_sync(background_tasks: BackgroundTasks) -> dict:
    """Trigger full data sync (runs in background)."""
    if _sync_state["running"]:
        return ok({"message": "同步已在进行中", "running": True})

    background_tasks.add_task(_run_full_sync)
    return ok({"message": "数据同步已启动", "running": True})


@router.post("/run")
async def run_full_sync_now(db: AsyncSession = Depends(get_db_session)) -> dict:
    """Run full data sync synchronously (wait for completion)."""
    if _sync_state["running"]:
        return ok({"message": "同步已在进行中", "running": True})

    result = await _do_full_sync(db)
    return ok(result)


async def _run_full_sync() -> None:
    """Background task wrapper for full sync."""
    from dependencies import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        await _do_full_sync(session)


async def _do_full_sync(db: AsyncSession) -> dict:
    """Execute full data sync sequentially."""
    from dependencies import get_session_factory
    from quant_os_infra_market.providers import ProviderFactory
    from quant_os_app_market.services.data_ingestion import DataIngestionService

    _sync_state["running"] = True
    _sync_state["error"] = None
    started = datetime.now()
    results = {}

    try:
        provider = ProviderFactory.get("akshare")

        # Each step uses its own session to avoid cascade rollbacks
        def _new_ingestion():
            from dependencies import get_session_factory
            factory = get_session_factory()
            return factory, DataIngestionService.__new__(DataIngestionService)

        # Step 1: Stock list
        logger.info("Sync step 1/5: stock list")
        try:
            from dependencies import get_session_factory
            factory = get_session_factory()
            async with factory() as step_session:
                step_ingestion = DataIngestionService(step_session, provider)
                res = await step_ingestion.sync_stock_list()
                await step_session.commit()
                results["stocks"] = res
                logger.info("Stock list sync: %s", res)
        except Exception as e:
            logger.error("Stock list sync failed: %s", e)
            results["stocks"] = {"error": str(e)}

        await asyncio.sleep(3)

        # Step 2: Northbound flow (own session)
        logger.info("Sync step 2/5: northbound flow")
        try:
            async with factory() as step_session:
                step_ingestion = DataIngestionService(step_session, provider)
                res = await step_ingestion.sync_northbound_flow()
                await step_session.commit()
                results["northbound"] = res
                logger.info("Northbound sync: %s", res)
        except Exception as e:
            logger.error("Northbound sync failed: %s", e)
            results["northbound"] = {"error": str(e)}

        await asyncio.sleep(5)

        # Step 3: Dragon tiger (own session)
        logger.info("Sync step 3/5: dragon tiger")
        try:
            async with factory() as step_session:
                step_ingestion = DataIngestionService(step_session, provider)
                res = await step_ingestion.sync_dragon_tiger()
                await step_session.commit()
                results["dragon_tiger"] = res
                logger.info("Dragon tiger sync: %s", res)
        except Exception as e:
            logger.error("Dragon tiger sync failed: %s", e)
            results["dragon_tiger"] = {"error": str(e)}

        await asyncio.sleep(2)

        # Step 4: OHLCV for sample stocks (own session per stock, longer delay)
        logger.info("Sync step 4/5: OHLCV sample data")
        await asyncio.sleep(5)  # Extra cooldown after previous AKShare calls
        try:
            sample_codes = ["000001.SZ", "600519.SH", "000858.SZ", "601318.SH", "000333.SZ"]
            synced = 0
            errors = []
            for code in sample_codes:
                for attempt in range(2):  # Retry once per stock
                    try:
                        async with factory() as step_session:
                            step_ingestion = DataIngestionService(step_session, provider)
                            res = await step_ingestion.sync_ohlcv_daily(ts_code=code)
                            await step_session.commit()
                            synced += 1
                            logger.info("OHLCV sync for %s: %s", code, res)
                            break
                    except Exception as e:
                        if attempt == 0:
                            logger.warning("OHLCV sync failed for %s, retrying: %s", code, e)
                            await asyncio.sleep(5)
                        else:
                            errors.append(f"{code}: {str(e)[:200]}")
                            logger.warning("OHLCV sync failed for %s: %s", code, e)
                await asyncio.sleep(3)

            results["ohlcv"] = {"synced_stocks": synced, "total_attempted": len(sample_codes), "errors": errors}
        except Exception as e:
            logger.error("OHLCV sync failed: %s", e)
            results["ohlcv"] = {"error": str(e)}

        duration = (datetime.now() - started).total_seconds()
        _sync_state["last_run"] = datetime.now().isoformat()
        _sync_state["last_duration_seconds"] = round(duration, 1)
        _sync_state["last_result"] = results
        _sync_state["error"] = None

        logger.info("Full sync completed in %.1fs: %s", duration, results)
        return {"status": "completed", "duration_seconds": round(duration, 1), "results": results}

    except Exception as e:
        _sync_state["error"] = str(e)
        logger.error("Full sync failed: %s", e)
        return {"status": "failed", "error": str(e)}

    finally:
        _sync_state["running"] = False


# ---------------------------------------------------------------------------
# Auto-sync scheduler (runs daily at market close)
# ---------------------------------------------------------------------------

async def scheduled_daily_sync() -> None:
    """Run daily sync at scheduled time."""
    while True:
        now = datetime.now()
        # Run at 16:00 (4 PM) every day after market close
        if now.hour == 16 and now.minute < 5:
            logger.info("Starting scheduled daily sync")
            from dependencies import get_session_factory
            factory = get_session_factory()
            async with factory() as session:
                await _do_full_sync(session)
            # Sleep 10 minutes to avoid running again within the same hour
            await asyncio.sleep(600)
        else:
            # Check every minute
            await asyncio.sleep(60)
