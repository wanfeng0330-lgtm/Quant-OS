"""Factor engine endpoints."""

from __future__ import annotations

import json
import math
from datetime import date
from typing import Any, Optional

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_db_session
from presentation.api_response import ok

router = APIRouter()


class FactorResponse(BaseModel):
    id: str
    factor_name: str
    display_name: str | None = None
    category: str
    description: str | None = None
    direction: int = 1
    is_active: bool = True
    version: int = 1

    model_config = {"from_attributes": True}


def _factor_to_api(factor) -> dict:
    return {
        "id": factor.id,
        "name": factor.factor_name,
        "factor_name": factor.factor_name,
        "display_name": factor.display_name,
        "category": factor.category,
        "description": factor.description or "",
        "direction": factor.direction,
        "is_active": factor.is_active,
        "version": factor.version,
        "parameters": factor.params or {},
    }


@router.get("")
@router.get("/")
async def list_factors(
    category: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    from sqlalchemy import select
    from quant_os_infra_factor.models import FactorModel
    from quant_os_app_factor.services.factor_catalog import sync_builtin_factors

    await sync_builtin_factors(db)

    query = select(FactorModel)
    if category:
        query = query.where(FactorModel.category == category)
    if is_active is not None:
        query = query.where(FactorModel.is_active == is_active)
    query = query.order_by(FactorModel.factor_name)

    result = await db.execute(query)
    factors = result.scalars().all()
    return ok([_factor_to_api(f) for f in factors])


# ---------------------------------------------------------------------------
# Factor Expression Evaluator (must be before /{factor_id} to avoid route conflict)
# ---------------------------------------------------------------------------

class ExpressionRequest(BaseModel):
    expression: str
    start_date: str = "2025-01-01"
    end_date: str = "2026-05-22"
    stock_pool: list[str] | None = None


# Supported factor functions
FACTOR_FUNCTIONS = {
    "ts_mean": "滚动均值",
    "ts_std": "滚动标准差",
    "ts_max": "滚动最大值",
    "ts_min": "滚动最小值",
    "ts_rank": "滚动排名",
    "ts_delta": "N日变化",
    "ts_corr": "滚动相关系数",
    "ts_cov": "滚动协方差",
    "rank": "截面排名",
    "delta": "差分",
    "log": "对数",
    "abs": "绝对值",
    "sign": "符号",
    "power": "幂次",
    "decay_linear": "线性衰减加权",
}


@router.get("/functions")
async def list_factor_functions() -> dict:
    """List supported factor expression functions."""
    funcs = [{"name": name, "description": desc} for name, desc in FACTOR_FUNCTIONS.items()]
    return ok(funcs)


@router.post("/evaluate")
async def evaluate_expression(
    request: ExpressionRequest,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Evaluate a custom factor expression against real market data."""
    from quant_os_infra_market.models.ohlcv_model import OHLCVDailyModel
    from sqlalchemy import select

    expr = request.expression.strip()
    if not expr:
        raise HTTPException(status_code=400, detail="Expression is required")

    query = (
        select(OHLCVDailyModel)
        .where(OHLCVDailyModel.trade_date >= request.start_date)
        .where(OHLCVDailyModel.trade_date <= request.end_date)
        .order_by(OHLCVDailyModel.ts_code, OHLCVDailyModel.trade_date)
    )
    if request.stock_pool:
        query = query.where(OHLCVDailyModel.ts_code.in_(request.stock_pool))

    result = await db.execute(query)
    rows = result.scalars().all()

    if not rows:
        return ok({"values": [], "count": 0, "expression": expr, "message": "No data found"})

    import pandas as pd

    data = [{
        "ts_code": r.ts_code,
        "trade_date": str(r.trade_date),
        "open": float(r.open) if r.open else 0,
        "high": float(r.high) if r.high else 0,
        "low": float(r.low) if r.low else 0,
        "close": float(r.close) if r.close else 0,
        "volume": float(r.volume) if r.volume else 0,
        "amount": float(r.amount) if r.amount else 0,
    } for r in rows]

    df = pd.DataFrame(data)

    try:
        factor_values = _eval_factor_expression(df, expr)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Expression error: {e}")

    output = []
    for _, row in factor_values.head(500).iterrows():
        val = row.get("factor_value")
        output.append({
            "ts_code": row["ts_code"],
            "trade_date": row["trade_date"],
            "value": float(val) if val is not None and not (isinstance(val, float) and math.isnan(val)) else None,
        })

    return ok({
        "values": output,
        "count": len(factor_values),
        "expression": expr,
        "coverage": f"{factor_values['factor_value'].notna().mean() * 100:.1f}%",
    })


def _eval_factor_expression(df: "pd.DataFrame", expr: str) -> "pd.DataFrame":
    """Evaluate a factor expression on panel data."""
    import pandas as pd

    fields = ["open", "high", "low", "close", "volume", "amount"]
    results = []
    for ts_code, group in df.groupby("ts_code"):
        g = group.sort_values("trade_date").copy()
        ctx = {f: g[f].values for f in fields}
        ctx["vwap"] = (g["amount"].values / g["volume"].replace(0, np.nan).values)

        try:
            val = _eval_expr(expr, ctx, len(g))
            g["factor_value"] = val
        except Exception:
            g["factor_value"] = np.nan

        results.append(g[["ts_code", "trade_date", "factor_value"]])

    if not results:
        return pd.DataFrame(columns=["ts_code", "trade_date", "factor_value"])
    return pd.concat(results, ignore_index=True)


def _eval_expr(expr: str, ctx: dict, n: int) -> np.ndarray:
    """Evaluate a factor expression with ts_* functions."""
    import re

    expr_clean = expr

    def replace_ts_func(match):
        func = match.group(1)
        args = [a.strip() for a in match.group(2).split(",")]
        # func is already "ts_mean", namespace has "_ts_mean"
        return "_ts_" + func[3:] + "(" + ", ".join(args) + ")"

    expr_clean = re.sub(r"(ts_\w+)\(([^)]+)\)", replace_ts_func, expr_clean)
    expr_clean = re.sub(r"rank\((\w+)\)", r"_rank(\1)", expr_clean)
    expr_clean = re.sub(r"delta\((\w+),\s*(\d+)\)", r"_delta(\1, \2)", expr_clean)
    expr_clean = re.sub(r"log\((\w+)\)", r"np.log(np.maximum(\1, 1e-10))", expr_clean)
    expr_clean = re.sub(r"abs\((\w+)\)", r"np.abs(\1)", expr_clean)
    expr_clean = re.sub(r"sign\((\w+)\)", r"np.sign(\1)", expr_clean)

    import pandas as pd

    namespace = {"np": np, **ctx}

    def _ts_mean(field, window):
        w = int(window)
        arr = ctx[field] if isinstance(field, str) and field in ctx else np.array(field)
        return pd.Series(arr).rolling(w, min_periods=1).mean().values

    def _ts_std(field, window):
        w = int(window)
        arr = ctx[field] if isinstance(field, str) and field in ctx else np.array(field)
        return pd.Series(arr).rolling(w, min_periods=1).std().values

    def _ts_max(field, window):
        w = int(window)
        arr = ctx[field] if isinstance(field, str) and field in ctx else np.array(field)
        return pd.Series(arr).rolling(w, min_periods=1).max().values

    def _ts_min(field, window):
        w = int(window)
        arr = ctx[field] if isinstance(field, str) and field in ctx else np.array(field)
        return pd.Series(arr).rolling(w, min_periods=1).min().values

    def _ts_rank(field, window):
        w = int(window)
        arr = ctx[field] if isinstance(field, str) and field in ctx else np.array(field)
        return pd.Series(arr).rolling(w, min_periods=1).apply(lambda x: x.rank(pct=True).iloc[-1], raw=False).values

    def _ts_delta(field, window):
        w = int(window)
        arr = ctx[field] if isinstance(field, str) and field in ctx else np.array(field)
        return pd.Series(arr).diff(w).values

    def _ts_corr(field1, field2, window):
        w = int(window)
        a = ctx[field1] if isinstance(field1, str) and field1 in ctx else np.array(field1)
        b = ctx[field2] if isinstance(field2, str) and field2 in ctx else np.array(field2)
        return pd.Series(a).rolling(w, min_periods=1).corr(pd.Series(b)).values

    def _rank(field):
        arr = ctx[field] if isinstance(field, str) and field in ctx else np.array(field)
        return pd.Series(arr).rank(pct=True).values

    def _delta(field, d):
        arr = ctx[field] if isinstance(field, str) and field in ctx else np.array(field)
        return pd.Series(arr).diff(int(d)).values

    def _decay_linear(field, window):
        w = int(window)
        arr = ctx[field] if isinstance(field, str) and field in ctx else np.array(field)
        weights = np.arange(1, w + 1, dtype=float)
        weights /= weights.sum()
        return pd.Series(arr).rolling(w, min_periods=1).apply(lambda x: np.dot(x[-w:], weights[-len(x):]), raw=True).values

    namespace.update({
        "_ts_mean": _ts_mean, "_ts_std": _ts_std, "_ts_max": _ts_max, "_ts_min": _ts_min,
        "_ts_rank": _ts_rank, "_ts_delta": _ts_delta, "_ts_corr": _ts_corr,
        "_rank": _rank, "_delta": _delta, "_decay_linear": _decay_linear,
    })

    result = eval(expr_clean, {"__builtins__": {}}, namespace)
    if isinstance(result, (int, float)):
        result = np.full(n, result)
    return np.asarray(result, dtype=float)


@router.get("/{factor_id}")
async def get_factor(
    factor_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    from sqlalchemy import select
    from quant_os_infra_factor.models import FactorModel

    result = await db.execute(select(FactorModel).where(FactorModel.id == factor_id))
    factor = result.scalar_one_or_none()
    if not factor:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Factor {factor_id} not found")
    return ok(_factor_to_api(factor))


class ComputeRequest(BaseModel):
    factor_ids: list[str] | None = None
    factor_name: str | None = None
    start_date: str
    end_date: str
    stock_pool: list[str] | dict | None = None
    params: dict | None = None


class ComputeResponse(BaseModel):
    job_id: str
    status: str
    message: str


@router.post("/compute")
async def compute_factors(
    request: ComputeRequest,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    from sqlalchemy import select
    from fastapi import HTTPException
    from quant_os_app_factor.services.factor_catalog import sync_builtin_factors
    from quant_os_app_factor.services.factor_compute_service import FactorComputeService
    from quant_os_domain_factor.entities.factor import FactorCategory, FactorDefinition, FactorDirection
    from quant_os_infra_factor.models import FactorModel
    from quant_os_infra_market.providers import ProviderFactory, ensure_providers_initialized

    await sync_builtin_factors(db)

    if request.factor_name:
        result = await db.execute(select(FactorModel).where(FactorModel.factor_name == request.factor_name))
    elif request.factor_ids:
        result = await db.execute(select(FactorModel).where(FactorModel.id == request.factor_ids[0]))
    else:
        raise HTTPException(status_code=400, detail="factor_name or factor_ids is required")

    factor = result.scalar_one_or_none()
    if not factor:
        raise HTTPException(status_code=404, detail="Factor not found")

    ensure_providers_initialized()
    provider = ProviderFactory.get()
    service = FactorComputeService(session=db, provider=provider)
    factor_def = FactorDefinition(
        factor_name=factor.factor_name,
        display_name=factor.display_name or factor.factor_name,
        category=FactorCategory(factor.category),
        description=factor.description or "",
        formula=factor.formula or "",
        direction=FactorDirection(factor.direction),
        params={**(factor.params or {}), **(request.params or {})},
    )
    stock_pool = request.stock_pool if isinstance(request.stock_pool, list) else None
    values = await service.compute_factor_values(
        factor_def=factor_def,
        start_date=date.fromisoformat(request.start_date),
        end_date=date.fromisoformat(request.end_date),
        stock_pool=stock_pool,
        factor_id=factor.id,
        store_to_db=True,
    )
    return ok(
        {
            "factor_name": factor.factor_name,
            "values": [
                {
                    "ts_code": row["ts_code"],
                    "trade_date": str(row["trade_date"]),
                    "value": None if row["value"] != row["value"] else float(row["value"]),
                }
                for _, row in values.head(500).iterrows()
            ],
            "count": len(values),
        }
    )


class AnalyzeRequest(BaseModel):
    factor_name: str | None = None
    factor_id: str | None = None
    start_date: str
    end_date: str
    method: str = "both"


@router.post("/analyze")
async def analyze_factor(
    request: AnalyzeRequest,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    from sqlalchemy import select
    from fastapi import HTTPException
    from quant_os_app_factor.services.factor_catalog import sync_builtin_factors
    from quant_os_app_factor.services.factor_compute_service import FactorComputeService
    from quant_os_infra_factor.models import FactorModel
    from quant_os_infra_market.providers import ProviderFactory, ensure_providers_initialized

    await sync_builtin_factors(db)
    query = select(FactorModel)
    if request.factor_id:
        query = query.where(FactorModel.id == request.factor_id)
    elif request.factor_name:
        query = query.where(FactorModel.factor_name == request.factor_name)
    else:
        raise HTTPException(status_code=400, detail="factor_name or factor_id is required")

    result = await db.execute(query)
    factor = result.scalar_one_or_none()
    if not factor:
        raise HTTPException(status_code=404, detail="Factor not found")

    ensure_providers_initialized()
    service = FactorComputeService(session=db, provider=ProviderFactory.get())
    analysis = await service.analyze_factor(
        factor_id=factor.id,
        start_date=date.fromisoformat(request.start_date),
        end_date=date.fromisoformat(request.end_date),
    )
    return ok(analysis)


# ---------------------------------------------------------------------------
# IC Analysis with time series
# ---------------------------------------------------------------------------

@router.get("/{factor_id}/ic-analysis")
async def get_ic_analysis(
    factor_id: str,
    start_date: str = Query("2025-01-01"),
    end_date: str = Query("2026-05-22"),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Get IC time series analysis for a factor."""
    from sqlalchemy import select, func
    from quant_os_infra_factor.models import FactorModel, FactorValueModel
    from quant_os_infra_market.models.ohlcv_model import OHLCVDailyModel

    result = await db.execute(select(FactorModel).where(FactorModel.id == factor_id))
    factor = result.scalar_one_or_none()
    if not factor:
        raise HTTPException(status_code=404, detail="Factor not found")

    # Get factor values
    fv_result = await db.execute(
        select(FactorValueModel)
        .where(FactorValueModel.factor_id == factor_id)
        .where(FactorValueModel.trade_date >= start_date)
        .where(FactorValueModel.trade_date <= end_date)
    )
    factor_values = fv_result.scalars().all()

    if not factor_values:
        return ok({
            "factor_name": factor.factor_name,
            "ic_series": [],
            "ic_mean": 0, "ic_std": 0, "icir": 0,
            "rank_ic_mean": 0, "ic_positive_ratio": 0,
        })

    # Build IC series by computing correlation with forward returns
    import pandas as pd

    fv_df = pd.DataFrame([{
        "ts_code": fv.ts_code,
        "trade_date": str(fv.trade_date),
        "factor_value": float(fv.value) if fv.value is not None else None,
    } for fv in factor_values])

    # Get forward returns (next day return)
    trade_dates = sorted(fv_df["trade_date"].unique())
    date_pairs = list(zip(trade_dates[:-1], trade_dates[1:]))

    # Get OHLCV for return calculation
    ohlcv_result = await db.execute(
        select(OHLCVDailyModel)
        .where(OHLCVDailyModel.trade_date >= start_date)
        .where(OHLCVDailyModel.trade_date <= end_date)
    )
    ohlcv_rows = ohlcv_result.scalars().all()

    ohlcv_df = pd.DataFrame([{
        "ts_code": r.ts_code,
        "trade_date": str(r.trade_date),
        "close": float(r.close) if r.close else 0,
    } for r in ohlcv_rows])

    if ohlcv_df.empty:
        return ok({
            "factor_name": factor.factor_name,
            "ic_series": [],
            "ic_mean": 0, "ic_std": 0, "icir": 0,
            "rank_ic_mean": 0, "ic_positive_ratio": 0,
        })

    # Calculate returns
    ohlcv_df = ohlcv_df.sort_values(["ts_code", "trade_date"])
    ohlcv_df["return_1d"] = ohlcv_df.groupby("ts_code")["close"].pct_change().shift(-1)

    # Merge factor with returns
    merged = fv_df.merge(
        ohlcv_df[["ts_code", "trade_date", "return_1d"]],
        on=["ts_code", "trade_date"],
        how="inner",
    ).dropna(subset=["factor_value", "return_1d"])

    # Calculate IC per date
    ic_series = []
    for td, group in merged.groupby("trade_date"):
        if len(group) < 10:
            continue
        ic = group["factor_value"].corr(group["return_1d"])
        rank_ic = group["factor_value"].corr(group["return_1d"], method="spearman")
        ic_series.append({
            "date": td,
            "ic": round(float(ic), 6) if not math.isnan(ic) else 0,
            "rank_ic": round(float(rank_ic), 6) if not math.isnan(rank_ic) else 0,
        })

    ic_df = pd.DataFrame(ic_series)
    if ic_df.empty:
        return ok({
            "factor_name": factor.factor_name,
            "ic_series": [],
            "ic_mean": 0, "ic_std": 0, "icir": 0,
            "rank_ic_mean": 0, "ic_positive_ratio": 0,
        })

    ic_mean = float(ic_df["ic"].mean())
    ic_std = float(ic_df["ic"].std())
    icir = ic_mean / ic_std if ic_std > 0 else 0
    rank_ic_mean = float(ic_df["rank_ic"].mean())
    ic_positive = float((ic_df["ic"] > 0).mean())

    return ok({
        "factor_name": factor.factor_name,
        "ic_series": ic_series,
        "ic_mean": round(ic_mean, 6),
        "ic_std": round(ic_std, 6),
        "icir": round(icir, 4),
        "rank_ic_mean": round(rank_ic_mean, 6),
        "ic_positive_ratio": round(ic_positive, 4),
        "periods": len(ic_series),
    })


# ---------------------------------------------------------------------------
# Layered Returns
# ---------------------------------------------------------------------------

@router.get("/{factor_id}/layered")
async def get_layered_returns(
    factor_id: str,
    start_date: str = Query("2025-01-01"),
    end_date: str = Query("2026-05-22"),
    layers: int = Query(5, ge=2, le=10),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Get layered (quantile) returns for a factor."""
    from sqlalchemy import select
    from quant_os_infra_factor.models import FactorModel, FactorValueModel
    from quant_os_infra_market.models.ohlcv_model import OHLCVDailyModel
    import pandas as pd

    result = await db.execute(select(FactorModel).where(FactorModel.id == factor_id))
    factor = result.scalar_one_or_none()
    if not factor:
        raise HTTPException(status_code=404, detail="Factor not found")

    # Get factor values
    fv_result = await db.execute(
        select(FactorValueModel)
        .where(FactorValueModel.factor_id == factor_id)
        .where(FactorValueModel.trade_date >= start_date)
        .where(FactorValueModel.trade_date <= end_date)
    )
    factor_values = fv_result.scalars().all()

    if not factor_values:
        return ok({"factor_name": factor.factor_name, "layers": [], "long_short": []})

    fv_df = pd.DataFrame([{
        "ts_code": fv.ts_code,
        "trade_date": str(fv.trade_date),
        "factor_value": float(fv.value) if fv.value is not None else None,
    } for fv in factor_values])

    # Get OHLCV
    ohlcv_result = await db.execute(
        select(OHLCVDailyModel)
        .where(OHLCVDailyModel.trade_date >= start_date)
        .where(OHLCVDailyModel.trade_date <= end_date)
    )
    ohlcv_rows = ohlcv_result.scalars().all()

    ohlcv_df = pd.DataFrame([{
        "ts_code": r.ts_code,
        "trade_date": str(r.trade_date),
        "close": float(r.close) if r.close else 0,
    } for r in ohlcv_rows])

    if ohlcv_df.empty:
        return ok({"factor_name": factor.factor_name, "layers": [], "long_short": []})

    ohlcv_df = ohlcv_df.sort_values(["ts_code", "trade_date"])
    ohlcv_df["return_1d"] = ohlcv_df.groupby("ts_code")["close"].pct_change().shift(-1)

    merged = fv_df.merge(
        ohlcv_df[["ts_code", "trade_date", "return_1d"]],
        on=["ts_code", "trade_date"],
        how="inner",
    ).dropna(subset=["factor_value", "return_1d"])

    # Assign quantile layers per date
    merged["layer"] = merged.groupby("trade_date")["factor_value"].transform(
        lambda x: pd.qcut(x, layers, labels=False, duplicates="drop") + 1
    )

    # Calculate layer returns
    layer_returns = []
    for layer_num in range(1, layers + 1):
        layer_data = merged[merged["layer"] == layer_num]
        if layer_data.empty:
            continue
        avg_return = float(layer_data["return_1d"].mean())
        cumulative = float((1 + layer_data.groupby("trade_date")["return_1d"].mean()).prod() - 1)
        layer_returns.append({
            "layer": layer_num,
            "avg_daily_return": round(avg_return * 100, 4),
            "cumulative_return": round(cumulative * 100, 2),
            "stocks_avg": int(layer_data.groupby("trade_date")["ts_code"].count().mean()),
        })

    # Long-short: top layer - bottom layer
    long_short = []
    if layer_returns:
        top = merged[merged["layer"] == layers].groupby("trade_date")["return_1d"].mean()
        bottom = merged[merged["layer"] == 1].groupby("trade_date")["return_1d"].mean()
        ls = (top - bottom).dropna()
        cumulative_ls = float((1 + ls).prod() - 1)
        long_short = {
            "avg_daily_return": round(float(ls.mean()) * 100, 4),
            "cumulative_return": round(cumulative_ls * 100, 2),
            "sharpe": round(float(ls.mean() / ls.std() * np.sqrt(252)), 4) if ls.std() > 0 else 0,
            "win_rate": round(float((ls > 0).mean()), 4),
        }

    return ok({
        "factor_name": factor.factor_name,
        "layers": layer_returns,
        "long_short": long_short,
        "total_periods": int(merged["trade_date"].nunique()),
    })
