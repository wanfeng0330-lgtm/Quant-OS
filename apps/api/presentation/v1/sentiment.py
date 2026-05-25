"""A-share market sentiment endpoints."""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from fastapi import APIRouter

from presentation.api_response import ok

router = APIRouter()


@router.get("/overview")
async def get_sentiment_overview() -> dict:
    """Get market sentiment overview."""
    now = datetime.now()
    # Simulated data — replace with real data source later
    limit_up = random.randint(15, 80)
    limit_down = random.randint(0, 25)
    consecutive_high = random.randint(3, 12)

    return ok({
        "date": now.strftime("%Y-%m-%d"),
        "limit_up_count": limit_up,
        "limit_down_count": limit_down,
        "consecutive_high": consecutive_high,
        "market_sentiment": "偏多" if limit_up > limit_down * 2 else ("偏空" if limit_down > limit_up else "中性"),
        "sentiment_score": round(min(100, max(0, 50 + (limit_up - limit_down) * 1.5 + consecutive_high * 2)), 1),
        "up_count": random.randint(2000, 3500),
        "down_count": random.randint(1200, 2800),
        "flat_count": random.randint(100, 300),
        "total_volume_billion": round(random.uniform(8000, 15000), 2),
        "total_amount_billion": round(random.uniform(600, 1200), 2),
    })


@router.get("/northbound")
async def get_northbound_flow() -> dict:
    """Get northbound capital flow data."""
    now = datetime.now()
    # Simulated 30-day northbound flow
    flows = []
    cumulative = 0
    for i in range(30, 0, -1):
        d = now - timedelta(days=i)
        if d.weekday() >= 5:
            continue
        net = round(random.uniform(-80, 120), 2)
        cumulative += net
        flows.append({
            "date": d.strftime("%Y-%m-%d"),
            "net_flow_billion": net,
            "cumulative_billion": round(cumulative, 2),
            "buy_billion": round(abs(net) + random.uniform(50, 150), 2),
            "sell_billion": round(abs(net) + random.uniform(50, 150) - net, 2),
        })

    today_net = round(random.uniform(-50, 80), 2)
    return ok({
        "today_net_flow_billion": today_net,
        "today_status": "净流入" if today_net > 0 else "净流出",
        "monthly_net_flow_billion": round(cumulative, 2),
        "flows": flows,
        "top_buy": [
            {"name": "贵州茅台", "net_buy_million": round(random.uniform(50, 200), 1)},
            {"name": "宁德时代", "net_buy_million": round(random.uniform(30, 150), 1)},
            {"name": "招商银行", "net_buy_million": round(random.uniform(20, 100), 1)},
            {"name": "中芯国际", "net_buy_million": round(random.uniform(15, 80), 1)},
            {"name": "比亚迪", "net_buy_million": round(random.uniform(10, 60), 1)},
        ],
        "top_sell": [
            {"name": "万科A", "net_sell_million": round(random.uniform(20, 80), 1)},
            {"name": "工商银行", "net_sell_million": round(random.uniform(15, 60), 1)},
            {"name": "中国平安", "net_sell_million": round(random.uniform(10, 50), 1)},
        ],
    })


@router.get("/dragon-tiger")
async def get_dragon_tiger() -> dict:
    """Get dragon-tiger list (龙虎榜) data."""
    now = datetime.now()
    stocks = [
        ("科大讯飞", "002230.SZ", "AI概念涨停"),
        ("中芯国际", "688981.SH", "半导体板块领涨"),
        ("宁德时代", "300750.SZ", "新能源龙头异动"),
        ("恒瑞医药", "600276.SH", "创新药利好"),
        ("比亚迪", "002594.SZ", "新能源汽车销量超预期"),
        ("立讯精密", "002475.SZ", "消费电子回暖"),
        ("药明康德", "603259.SH", "CXO板块反弹"),
        ("海康威视", "002415.SZ", "AI安防概念"),
    ]

    entries = []
    for name, code, reason in stocks[:random.randint(4, 8)]:
        entries.append({
            "ts_code": code,
            "name": name,
            "pct_chg": round(random.uniform(5, 10), 2),
            "turnover_rate": round(random.uniform(5, 25), 2),
            "net_buy_million": round(random.uniform(50, 500), 1),
            "reason": reason,
            "date": now.strftime("%Y-%m-%d"),
        })

    return ok({
        "date": now.strftime("%Y-%m-%d"),
        "entries": entries,
        "summary": f"今日龙虎榜共 {len(entries)} 只个股上榜，机构净买入为主。",
    })


@router.get("/industry-rotation")
async def get_industry_rotation() -> dict:
    """Get industry rotation analysis."""
    industries = [
        "人工智能", "半导体", "新能源", "医药生物", "消费电子",
        "银行", "房地产", "煤炭", "钢铁", "建材",
        "军工", "汽车", "家电", "食品饮料", "传媒",
        "通信", "计算机", "电子", "机械", "化工",
    ]

    now = datetime.now()
    rotation = []
    for ind in industries:
        rotation.append({
            "name": ind,
            "pct_1d": round(random.uniform(-4, 6), 2),
            "pct_5d": round(random.uniform(-8, 12), 2),
            "pct_20d": round(random.uniform(-15, 25), 2),
            "turnover_rate": round(random.uniform(1, 8), 2),
            "net_flow_million": round(random.uniform(-500, 800), 1),
            "momentum": random.choice(["强势", "震荡", "弱势"]),
        })

    rotation.sort(key=lambda x: x["pct_1d"], reverse=True)

    return ok({
        "date": now.strftime("%Y-%m-%d"),
        "industries": rotation,
        "hot_sectors": [i["name"] for i in rotation[:3]],
        "cold_sectors": [i["name"] for i in rotation[-3:]],
    })


@router.get("/limit-stats")
async def get_limit_stats() -> dict:
    """Get limit up/down statistics."""
    now = datetime.now()

    # Simulated limit up/down breakdown
    limit_up_stocks = [
        {"name": "科大讯飞", "ts_code": "002230.SZ", "reason": "AI概念", "consecutive": 3},
        {"name": "中芯国际", "ts_code": "688981.SH", "reason": "半导体", "consecutive": 1},
        {"name": "浪潮信息", "ts_code": "000977.SZ", "reason": "AI算力", "consecutive": 2},
        {"name": "紫光股份", "ts_code": "000938.SZ", "reason": "信创", "consecutive": 1},
        {"name": "中科曙光", "ts_code": "603019.SH", "reason": "AI服务器", "consecutive": 4},
    ]

    limit_down_stocks = [
        {"name": "万科A", "ts_code": "000002.SZ", "reason": "行业利空"},
        {"name": "华夏幸福", "ts_code": "600340.SH", "reason": "债务风险"},
    ]

    return ok({
        "date": now.strftime("%Y-%m-%d"),
        "limit_up_count": len(limit_up_stocks) + random.randint(10, 50),
        "limit_down_count": len(limit_down_stocks) + random.randint(0, 10),
        "consecutive_high": max(s["consecutive"] for s in limit_up_stocks),
        "limit_up_stocks": limit_up_stocks,
        "limit_down_stocks": limit_down_stocks,
        "limit_up_reasons": {
            "AI概念": random.randint(5, 15),
            "半导体": random.randint(3, 10),
            "新能源": random.randint(2, 8),
            "其他": random.randint(5, 20),
        },
    })
