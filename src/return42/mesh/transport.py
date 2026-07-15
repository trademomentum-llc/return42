"""Mesh transport abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Awaitable, Callable

from .message import MeshMessage


Handler = Callable[[MeshMessage], Awaitable[None]]


class MeshTransport(ABC):
    """Abstract transport for mesh messages."""

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def publish(self, message: MeshMessage) -> None: ...

    @abstractmethod
    async def subscribe(self, topic: str, handler: Handler) -> None: ...

    @abstractmethod
    async def unsubscribe(self, topic: str, handler: Handler) -> None: ...


class InMemoryTransport(MeshTransport):
    """In-memory transport for tests and single-process sandboxes."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Handler]] = defaultdict(list)
        self._running = False

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def publish(self, message: MeshMessage) -> None:
        if not self._running:
            raise RuntimeError("Transport not started")
        handlers = self._subscribers.get(message.topic, [])
        for handler in handlers:
            await handler(message)

    async def subscribe(self, topic: str, handler: Handler) -> None:
        self._subscribers[topic].append(handler)

    async def unsubscribe(self, topic: str, handler: Handler) -> None:
        handlers = self._subscribers.get(topic, [])
        if handler in handlers:
            handlers.remove(handler)
