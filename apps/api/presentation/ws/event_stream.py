"""Global event stream WebSocket — broadcasts system-wide research events."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

# ---------------------------------------------------------------------------
# Global event bus: list of queues per subscriber
# ---------------------------------------------------------------------------
_subscribers: list[asyncio.Queue] = []
_event_history: list[dict[str, Any]] = []  # last N events for new subscribers
MAX_HISTORY = 50


def publish_event(event_type: str, data: dict[str, Any]) -> None:
    """Publish an event to all connected subscribers."""
    event = {
        "type": event_type,
        "time": datetime.now().isoformat(),
        **data,
    }
    _event_history.append(event)
    if len(_event_history) > MAX_HISTORY:
        _event_history.pop(0)

    for q in _subscribers:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass


@router.websocket("/ws/events")
async def event_stream(ws: WebSocket) -> None:
    """WebSocket endpoint for real-time event streaming."""
    await ws.accept()
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    _subscribers.append(queue)

    # Send recent history on connect
    for event in _event_history[-20:]:
        await ws.send_json(event)

    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30)
                await ws.send_json(event)
            except asyncio.TimeoutError:
                await ws.send_json({"type": "ping"})
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        if queue in _subscribers:
            _subscribers.remove(queue)


# ---------------------------------------------------------------------------
# Event types for convenience
# ---------------------------------------------------------------------------
def emit_factor_computed(factor_name: str, stock_count: int, duration_ms: int) -> None:
    publish_event("factor_computed", {
        "category": "factor",
        "message": f"因子 {factor_name} 计算完成，覆盖 {stock_count} 只股票，耗时 {duration_ms}ms",
        "data": {"factor_name": factor_name, "stock_count": stock_count, "duration_ms": duration_ms},
    })


def emit_workflow_started(workflow_name: str, run_id: str) -> None:
    publish_event("workflow_started", {
        "category": "workflow",
        "message": f"工作流 {workflow_name} 开始执行",
        "data": {"workflow_name": workflow_name, "run_id": run_id},
    })


def emit_workflow_completed(workflow_name: str, run_id: str, duration_ms: int) -> None:
    publish_event("workflow_completed", {
        "category": "workflow",
        "message": f"工作流 {workflow_name} 执行完成，耗时 {duration_ms}ms",
        "data": {"workflow_name": workflow_name, "run_id": run_id, "duration_ms": duration_ms},
    })


def emit_report_generated(report_title: str, report_id: str) -> None:
    publish_event("report_generated", {
        "category": "report",
        "message": f"研究报告 {report_title} 生成完成",
        "data": {"report_title": report_title, "report_id": report_id},
    })


def emit_market_alert(alert_type: str, message: str, data: dict | None = None) -> None:
    publish_event("market_alert", {
        "category": "market",
        "message": message,
        "data": data or {},
    })


def emit_system_event(message: str, level: str = "info") -> None:
    publish_event("system_event", {
        "category": "system",
        "level": level,
        "message": message,
    })
