"""MQTT-based mesh transport using aiomqtt."""

from __future__ import annotations

import json
import os

from aiomqtt import Client

from .message import MeshMessage
from .transport import Handler, MeshTransport


class MqttTransport(MeshTransport):
    """Mesh transport over MQTT."""

    def __init__(self, host: str | None = None, port: int | None = None, node_id: str | None = None) -> None:
        self._host = host or os.getenv("MQTT_HOST", "127.0.0.1")
        self._port = port or int(os.getenv("MQTT_PORT", "1883"))
        self._node_id = node_id or os.getenv("NODE_ID", "anonymous")
        self._client: Client | None = None
        self._handlers: list[tuple[str, Handler]] = []

    def _encode(self, message: MeshMessage) -> bytes:
        return message.model_dump_json().encode("utf-8")

    def _decode(self, data: bytes) -> MeshMessage:
        return MeshMessage.model_validate_json(data)

    async def start(self) -> None:
        self._client = Client(hostname=self._host, port=self._port)
        await self._client.__aenter__()

    async def stop(self) -> None:
        if self._client is not None:
            await self._client.__aexit__(None, None, None)
            self._client = None

    async def publish(self, message: MeshMessage) -> None:
        if self._client is None:
            raise RuntimeError("Transport not started")
        await self._client.publish(message.topic, self._encode(message))

    async def subscribe(self, topic: str, handler: Handler) -> None:
        if self._client is None:
            raise RuntimeError("Transport not started")
        self._handlers.append((topic, handler))
        await self._client.subscribe(topic)

    async def unsubscribe(self, topic: str, handler: Handler) -> None:
        entry = (topic, handler)
        if entry not in self._handlers:
            return
        self._handlers.remove(entry)
        if self._client is not None and not any(t == topic for t, _ in self._handlers):
            await self._client.unsubscribe(topic)
