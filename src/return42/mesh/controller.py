"""SOM mesh controller."""

from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable

from return42.observability.telemetry import TelemetryBus, TelemetryEvent, EventLevel

from .identity import NodeIdentity
from .message import MeshMessage, MessageTopic
from .transport import MeshTransport


MessageHandler = Callable[[MeshMessage], Awaitable[None]]


class SmeshController:
    """Controls a single SOM node in the mesh."""

    def __init__(
        self,
        identity: NodeIdentity,
        transport: MeshTransport,
        heartbeat_interval: float = 1.0,
        telemetry_bus: TelemetryBus | None = None,
    ) -> None:
        self._identity = identity
        self._transport = transport
        self._heartbeat_interval = heartbeat_interval
        self._telemetry = telemetry_bus or TelemetryBus()
        self._peers: dict[str, float] = {}
        self._handlers: dict[str, list[MessageHandler]] = {}
        self._heartbeat_task: asyncio.Task | None = None
        self._running = False

    @property
    def peers(self) -> set[str]:
        return set(self._peers.keys())

    async def start(self) -> None:
        self._running = True
        await self._transport.start()
        await self._transport.subscribe(MessageTopic.HEARTBEAT.value, self._on_heartbeat)
        await self._transport.subscribe(MessageTopic.DISCOVERY.value, self._on_discovery)
        await self._transport.subscribe(MessageTopic.COMMAND.value, self._on_command)
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        await self._announce()

    async def stop(self) -> None:
        self._running = False
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        await self._transport.unsubscribe(MessageTopic.HEARTBEAT.value, self._on_heartbeat)
        await self._transport.unsubscribe(MessageTopic.DISCOVERY.value, self._on_discovery)
        await self._transport.unsubscribe(MessageTopic.COMMAND.value, self._on_command)
        await self._transport.stop()

    async def send(self, topic: MessageTopic, payload: dict, destination: str | None = None) -> None:
        msg = MeshMessage(
            source=self._identity.node_id,
            destination=destination,
            topic=topic,
            payload=payload,
        )
        await self._transport.publish(msg)
        self._emit_telemetry("mesh.message.sent", {"topic": topic.value, "destination": destination})

    def on_message(self, topic: MessageTopic, handler: MessageHandler) -> None:
        self._handlers.setdefault(topic.value, []).append(handler)

    async def _heartbeat_loop(self) -> None:
        while self._running:
            await self.send(MessageTopic.HEARTBEAT, {"ts": time.time()})
            await asyncio.sleep(self._heartbeat_interval)

    async def _announce(self) -> None:
        await self.send(MessageTopic.DISCOVERY, {"public_key": self._identity.public_key})

    async def _on_heartbeat(self, msg: MeshMessage) -> None:
        if msg.source == self._identity.node_id:
            return
        self._peers[msg.source] = time.time()
        await self._dispatch_user_handlers(msg.topic, msg)

    async def _on_discovery(self, msg: MeshMessage) -> None:
        if msg.source == self._identity.node_id:
            return
        is_new = msg.source not in self._peers
        self._peers[msg.source] = time.time()
        if is_new:
            await self._announce()
        await self._dispatch_user_handlers(msg.topic, msg)

    async def _on_command(self, msg: MeshMessage) -> None:
        await self._dispatch_user_handlers(msg.topic, msg)

    async def _dispatch_user_handlers(self, topic: MessageTopic | str, msg: MeshMessage) -> None:
        handlers = self._handlers.get(topic, [])
        for handler in handlers:
            await handler(msg)

    def _emit_telemetry(self, name: str, payload: dict) -> None:
        event = TelemetryEvent(
            name=name,
            source=self._identity.node_id,
            level=EventLevel.INFO,
            payload=payload,
        )
        self._telemetry.publish(event)
