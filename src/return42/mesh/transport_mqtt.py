"""MQTT-based mesh transport using aiomqtt."""

from __future__ import annotations

import asyncio
import json
import logging
import os

from aiomqtt import Client, Message

from .message import MeshMessage
from .transport import Handler, MeshTransport

logger = logging.getLogger(__name__)


class MqttTransport(MeshTransport):
    """Mesh transport over MQTT."""

    def __init__(self, host: str | None = None, port: int | None = None, node_id: str | None = None) -> None:
        self._host = host or os.getenv("MQTT_HOST", "127.0.0.1")
        self._port = port or int(os.getenv("MQTT_PORT", "1883"))
        self._node_id = node_id or os.getenv("NODE_ID", "anonymous")
        self._client: Client | None = None
        self._handlers: list[tuple[str, Handler]] = []
        self._receive_task: asyncio.Task | None = None

    def _encode(self, message: MeshMessage) -> bytes:
        return message.model_dump_json().encode("utf-8")

    def _decode(self, data: bytes) -> MeshMessage:
        return MeshMessage.model_validate_json(data)

    async def start(self) -> None:
        client = Client(hostname=self._host, port=self._port)
        await client.__aenter__()
        self._client = client
        # Subscribe any handlers registered before start.
        for topic, _ in self._handlers:
            await self._client.subscribe(topic)
        self._receive_task = asyncio.create_task(self._receive_loop())

    async def stop(self) -> None:
        if self._receive_task is not None:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None
        if self._client is not None:
            await self._client.__aexit__(None, None, None)
            self._client = None

    async def publish(self, message: MeshMessage) -> None:
        if self._client is None:
            raise RuntimeError("Transport not started")
        await self._client.publish(message.topic, self._encode(message))

    async def subscribe(self, topic: str, handler: Handler) -> None:
        self._handlers.append((topic, handler))
        if self._client is not None:
            await self._client.subscribe(topic)

    async def unsubscribe(self, topic: str, handler: Handler) -> None:
        entry = (topic, handler)
        if entry not in self._handlers:
            return
        self._handlers.remove(entry)
        if self._client is not None and not any(t == topic for t, _ in self._handlers):
            await self._client.unsubscribe(topic)

    async def _receive_loop(self) -> None:
        if self._client is None:
            return
        try:
            async for message in self._client.messages:
                await self._dispatch_message(message)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover - broker disconnect handling
            logger.warning("MQTT receive loop exited with error: %s", exc)

    async def _dispatch_message(self, message: Message) -> None:
        topic = str(message.topic)
        try:
            mesh_msg = self._decode(message.payload)
        except Exception as exc:
            logger.warning("Failed to decode MQTT message on %s: %s", topic, exc)
            return
        for registered_topic, handler in self._handlers:
            if registered_topic == topic:
                try:
                    await handler(mesh_msg)
                except Exception as exc:
                    logger.warning("Handler for topic %s raised an error: %s", topic, exc)
