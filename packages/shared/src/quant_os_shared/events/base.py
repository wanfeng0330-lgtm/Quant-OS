"""Domain event and integration event base classes."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class DomainEvent(BaseModel):
    """Base class for domain events within a bounded context."""
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="")
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}

    def __init__(self, **data: Any) -> None:
        if "event_type" not in data or not data["event_type"]:
            data["event_type"] = self.__class__.__name__
        super().__init__(**data)


class IntegrationEvent(DomainEvent):
    """Base class for events that cross bounded context boundaries."""
    source_context: str = ""
    target_contexts: list[str] = Field(default_factory=list)
