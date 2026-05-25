"""Auto-sync stock data from baostock on demand."""

from __future__ import annotations

import json
import logging
import subprocess
from datetime import date

logger = logging.getLogger(__name__)


def _to_bs_code(ts_code: str) -> str:
    if ts_code.endswith(".SZ"):
        return "sz." + ts_code.replace(".SZ", "")
    return "sh." + ts_code.replace(".SH", "")


def _build_script(codes: dict, start: str, end: str) -> str:
    codes_json = json.dumps(codes)
    return (
        "import baostock as bs\n"
        "import json\n"
        "\n"
        "bs.login()\n"
        "results = {}\n"
        f"codes = json.loads('{codes_json}')\n"
        "for ts_code, bs_code in codes.items():\n"
        "    try:\n"
        '        rs = bs.query_history_k_data_plus(bs_code,\n'
        '            "date,open,high,low,close,volume,amount",\n'
        f'            start_date="{start}", end_date="{end}",\n'
        '            frequency="d", adjustflag="2")\n'
        "        rows = []\n"
        '        while rs.error_code == "0" and rs.next():\n'
        "            r = rs.get_row_data()\n"
        "            rows.append([r[0], float(r[1]), float(r[2]), float(r[3]), float(r[4]), int(float(r[5])), float(r[6])])\n"
        "        results[ts_code] = rows\n"
        "    except:\n"
        "        results[ts_code] = []\n"
        "bs.logout()\n"
        "print(json.dumps(results))\n"
    )


def sync_stock_ohlcv(ts_code: str, start: str = "2025-01-01", end: str | None = None) -> list[dict]:
    """Fetch daily OHLCV from baostock via subprocess."""
    if end is None:
        end = date.today().isoformat()

    bs_code = _to_bs_code(ts_code)
    script = _build_script({ts_code: bs_code}, start, end)

    try:
        result = subprocess.run(
            ["python", "-c", script],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            logger.warning("baostock sync failed: %s", result.stderr[:300])
            return []

        stdout = result.stdout.strip()
        # baostock prints "login success!" / "logout success!" to stdout
        # Find the JSON line (starts with '{')
        json_start = stdout.find('{')
        if json_start < 0:
            return []
        data = json.loads(stdout[json_start:])
        rows = data.get(ts_code, [])
        return [
            {
                "ts_code": ts_code,
                "trade_date": r[0],
                "open": r[1],
                "high": r[2],
                "low": r[3],
                "close": r[4],
                "volume": r[5],
                "amount": r[6],
            }
            for r in rows
        ]
    except Exception as e:
        logger.error("sync_stock_ohlcv error: %s", e)
        return []


def batch_sync_stocks(ts_codes: list[str], start: str = "2025-01-01", end: str | None = None) -> dict:
    """Batch sync OHLCV for multiple stocks via subprocess."""
    if end is None:
        end = date.today().isoformat()

    codes = {tc: _to_bs_code(tc) for tc in ts_codes}
    script = _build_script(codes, start, end)

    try:
        result = subprocess.run(
            ["python", "-c", script],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            logger.warning("batch sync failed: %s", result.stderr[:300])
            return {"synced": 0, "error": result.stderr[:300]}

        stdout = result.stdout.strip()
        json_start = stdout.find('{')
        if json_start < 0:
            return {"synced": 0, "error": "No JSON output"}
        data = json.loads(stdout[json_start:])
        synced = sum(1 for v in data.values() if v)
        return {"synced": synced, "total": len(ts_codes), "details": {k: len(v) for k, v in data.items() if v}}
    except Exception as e:
        logger.error("batch_sync_stocks error: %s", e)
        return {"synced": 0, "error": str(e)}
