"""SOM mesh controller."""

from __future__ import annotations

import asyncio
import inspect
import time
from typing import Awaitable, Callable

from return42.observability.metrics import MetricsRegistry, get_registry
from return42.observability.telemetry import TelemetryBus, TelemetryEvent, EventLevel

from .identity import NodeIdentity
from .message import MeshMessage, MessageTopic
from .transport import MeshTransport


MessageHandler = Callable[[MeshMessage], Awaitable[None] | None]


class SmeshController:
    """Controls a single SOM node in the mesh."""

    def __init__(
        self,
        identity: NodeIdentity,
        transport: MeshTransport,
        heartbeat_interval: float = 1.0,
        peer_timeout: float | None = None,
        telemetry_bus: TelemetryBus | None = None,
        registry: MetricsRegistry | None = None,
    ) -> None:
        self._identity = identity
        self._transport = transport
        self._heartbeat_interval = heartbeat_interval
        self._peer_timeout = peer_timeout if peer_timeout is not None else 3 * heartbeat_interval
        self._telemetry = telemetry_bus or TelemetryBus()
        self._registry = registry or get_registry()
        self._sent_counter = self._registry.counter(
            "mesh_messages_sent_total",
            "Total mesh messages published by this node",
            ("node_id", "topic", "destination_type"),
        )
        self._received_counter = self._registry.counter(
            "mesh_messages_received_total",
            "Total mesh messages received by this node",
            ("node_id", "topic"),
        )
        self._peer_gauge = self._registry.gauge(
            "mesh_peers_count",
            "Number of known non-stale peers",
            ("node_id",),
        )
        self._peers: dict[str, float] = {}
        self._handlers: dict[str, list[MessageHandler]] = {}
        self._heartbeat_task: asyncio.Task | None = None
        self._running = False

    @property
    def node_id(self) -> str:
        return self._identity.node_id

    @property
    def peers(self) -> set[str]:
        now = time.time()
        return {
            node_id
            for node_id, last_seen in self._peers.items()
            if now - last_seen <= self._peer_timeout
        }

    async def start(self) -> None:
        if self._running:
            raise RuntimeError("Controller already started")

        self._running = True
        try:
            await self._transport.start()
            for topic in MessageTopic:
                await self._transport.subscribe(topic.value, self._on_message)

            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            await self._announce()
        except Exception:
            await self.stop()
            raise

    async def stop(self) -> None:
        if not self._running and self._heartbeat_task is None:
            return

        self._running = False
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None
        for topic in MessageTopic:
            await self._transport.unsubscribe(topic.value, self._on_message)
        await self._transport.stop()

    async def send(self, topic: MessageTopic, payload: dict, destination: str | None = None) -> None:
        msg = MeshMessage(
            source=self._identity.node_id,
            destination=destination,
            topic=topic,
            payload=payload,
        )
        await self._transport.publish(msg)
        destination_type = "direct" if destination else "broadcast"
        self._sent_counter.labels(
            node_id=self.node_id,
            topic=topic.value,
            destination_type=destination_type,
        ).inc()
        self._emit_telemetry("mesh.message.sent", {"topic": topic.value, "destination": destination})

    def on_message(self, topic: MessageTopic, handler: MessageHandler) -> None:
        self._handlers.setdefault(topic.value, []).append(handler)

    async def _heartbeat_loop(self) -> None:
        while self._running:
            self._prune_peers()
            await self.send(MessageTopic.HEARTBEAT, {"ts": time.time()})
            await asyncio.sleep(self._heartbeat_interval)

    def _prune_peers(self) -> None:
        now = time.time()
        stale = [
            node_id
            for node_id, last_seen in self._peers.items()
            if now - last_seen > self._peer_timeout
        ]
        for node_id in stale:
            del self._peers[node_id]
        self._update_peer_gauge()

    def _update_peer_gauge(self) -> None:
        self._peer_gauge.labels(node_id=self.node_id).set(len(self.peers))

    async def _announce(self) -> None:
        await self.send(MessageTopic.DISCOVERY, {"public_key": self._identity.public_key})

    def _is_targeted_at_me(self, msg: MeshMessage) -> bool:
        return msg.destination is None or msg.destination == self._identity.node_id

    async def _on_message(self, msg: MeshMessage) -> None:
        if not self._is_targeted_at_me(msg):
            return
        if msg.source == self._identity.node_id:
            return

        self._received_counter.labels(
            node_id=self.node_id,
            topic=msg.topic.value,
        ).inc()
        self._emit_telemetry(
            "mesh.message.received",
            {"topic": msg.topic.value, "source": msg.source, "destination": msg.destination},
        )

        if msg.topic == MessageTopic.HEARTBEAT:
            await self._on_heartbeat(msg)
        elif msg.topic == MessageTopic.DISCOVERY:
            await self._on_discovery(msg)
        elif msg.topic == MessageTopic.COMMAND:
            await self._on_command(msg)
        else:
            await self._dispatch_user_handlers(msg.topic.value, msg)

    async def _on_heartbeat(self, msg: MeshMessage) -> None:
        self._peers[msg.source] = time.time()
        self._update_peer_gauge()
        await self._dispatch_user_handlers(msg.topic.value, msg)

    async def _on_discovery(self, msg: MeshMessage) -> None:
        is_new = msg.source not in self._peers
        self._peers[msg.source] = time.time()
        self._update_peer_gauge()
        if is_new:
            await self._announce()
        await self._dispatch_user_handlers(msg.topic.value, msg)

    async def _on_command(self, msg: MeshMessage) -> None:
        await self._dispatch_user_handlers(msg.topic.value, msg)

    async def _dispatch_user_handlers(self, topic: str, msg: MeshMessage) -> None:
        handlers = self._handlers.get(topic, [])
        for handler in handlers:
            if inspect.iscoroutinefunction(handler):
                await handler(msg)
            else:
                handler(msg)

    def _emit_telemetry(self, name: str, payload: dict) -> None:
        event = TelemetryEvent(
            name=name,
            source=self._identity.node_id,
            level=EventLevel.INFO,
            payload=payload,
        )
        self._telemetry.publish(event)
