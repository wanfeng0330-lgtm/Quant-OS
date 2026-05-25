"""Small response helpers matching the frontend API contract."""

from __future__ import annotations

from typing import Any


def ok(data: Any = None, message: str | None = None) -> dict[str, Any]:
    response: dict[str, Any] = {"success": True}
    if data is not None:
        response["data"] = data
    if message:
        response["message"] = message
    return response


def fail(error: str, message: str | None = None) -> dict[str, Any]:
    return {"success": False, "error": error, "message": message or error}
