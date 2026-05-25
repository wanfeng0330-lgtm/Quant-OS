"""Event bus implementation (in-process + Redis)."""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from typing import Any, Callable, Coroutine

from quant_os_shared.events.base import DomainEvent, IntegrationEvent

logger = logging.getLogger(__name__)

EventHandler = Callable[[DomainEvent], Coroutine[Any, Any, None]]


class EventBus:
    """In-process event bus with optional Redis pub/sub integration."""

    def __init__(self, redis_client: Any | None = None) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._redis = redis_client
        self._redis_channel_prefix = "quant_os:events:"

    def subscribe(self, event_type: type[DomainEvent], handler: EventHandler) -> None:
        type_name = event_type.__name__
        self._handlers[type_name].append(handler)
        logger.debug("Subscribed %s to %s", handler.__qualname__, type_name)

    def unsubscribe(self, event_type: type[DomainEvent], handler: EventHandler) -> None:
        type_name = event_type.__name__
        if handler in self._handlers[type_name]:
            self._handlers[type_name].remove(handler)

    async def publish(self, event: DomainEvent) -> None:
        event_type = event.event_type
        handlers = self._handlers.get(event_type, [])
        if not handlers:
            logger.debug("No handlers for event %s", event_type)
            return
        logger.info("Publishing event %s to %d handlers", event_type, len(handlers))
        results = await asyncio.gather(
            *(self._safe_call(handler, event) for handler in handlers),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, Exception):
                logger.error("Event handler error for %s: %s", event_type, result)

        if isinstance(event, IntegrationEvent) and self._redis:
            await self._publish_to_redis(event)

    async def publish_integration(self, event: IntegrationEvent) -> None:
        await self.publish(event)

    async def _safe_call(self, handler: EventHandler, event: DomainEvent) -> None:
        try:
            await handler(event)
        except Exception as exc:
            logger.error("Handler %s failed: %s", handler.__qualname__, exc, exc_info=True)
            raise

    async def _publish_to_redis(self, event: IntegrationEvent) -> None:
        if not self._redis:
            return
        channel = f"{self._redis_channel_prefix}{event.event_type}"
        data = event.model_dump_json()
        try:
            await self._redis.publish(channel, data)
            logger.debug("Published integration event to Redis: %s", channel)
        except Exception as exc:
            logger.error("Failed to publish to Redis: %s", exc)
