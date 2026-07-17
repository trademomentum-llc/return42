"""Typed in-memory telemetry bus."""

from __future__ import annotations

import time
from collections import defaultdict
from enum import Enum
from typing import Any, Callable

from pydantic import BaseModel, Field


class EventLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


class TelemetryEvent(BaseModel):
    name: str
    timestamp: float = Field(default_factory=time.time)
    source: str
    level: EventLevel = EventLevel.INFO
    payload: dict[str, Any] = Field(default_factory=dict)


class TelemetryBus:
    """In-memory pub/sub bus for telemetry events."""

    def __init__(self) -> None:
        # Accepts both synchronous callbacks and coroutines. Coroutine results are
        # currently fire-and-forget; callers requiring awaited delivery should use
        # an async subscriber wrapper in the future.
        self._subscriptions: dict[str, list[Callable[[TelemetryEvent], Any]]] = defaultdict(list)
        self._history: list[TelemetryEvent] = []

    def subscribe(
        self,
        name: str,
        callback: Callable[[TelemetryEvent], Any],
    ) -> None:
        """Subscribe to telemetry events.

        `callback` may be a synchronous callable or an async coroutine function.
        """
        self._subscriptions[name].append(callback)

    def publish(self, event: TelemetryEvent) -> None:
        self._history.append(event)
        for callback in self._subscriptions.get(event.name, []):
            result = callback(event)
            if result is not None:
                # Fire-and-forget async handlers are not awaited here;
                # callers awaiting delivery should use subscribe_async in future tasks.
                pass

    def events(self, name: str | None = None) -> list[TelemetryEvent]:
        if name is None:
            return list(self._history)
        return [e for e in self._history if e.name == name]
