"""WebSocket endpoint for real-time workflow execution streaming."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from presentation.v1.workflows import _run_event_queues

router = APIRouter()


@router.websocket("/ws/workflow/{run_id}")
async def workflow_stream(ws: WebSocket, run_id: str) -> None:
    """Stream workflow execution events to client via WebSocket.

    Events:
        - node_start: A node begins execution
        - node_complete: A node finishes
        - node_result: Node output data
        - log: Log message
        - status: Workflow status change
    """
    await ws.accept()

    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    _run_event_queues.setdefault(run_id, []).append(queue)

    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                await ws.send_json(event)
                if event.get("type") == "status" and event.get("status") in ("completed", "failed", "cancelled"):
                    # Final event — send done marker then close
                    await ws.send_json({"type": "done"})
                    break
            except asyncio.TimeoutError:
                # Send keepalive ping
                await ws.send_json({"type": "ping"})
    except WebSocketDisconnect:
        pass
    finally:
        queues = _run_event_queues.get(run_id, [])
        if queue in queues:
            queues.remove(queue)
        if not queues:
            _run_event_queues.pop(run_id, None)
