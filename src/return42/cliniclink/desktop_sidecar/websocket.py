from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from fastapi import WebSocket


class EventManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def broadcast(self, event_type: str, payload: dict) -> None:
        event = {
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }
        message = json.dumps(event)
        # Copy set because disconnect may mutate it
        for conn in list(self._connections):
            try:
                await conn.send_text(message)
            except Exception:
                self.disconnect(conn)


MANAGER = EventManager()
