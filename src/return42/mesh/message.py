"""Mesh message schema."""

from __future__ import annotations

import time
import uuid
from enum import Enum

from pydantic import BaseModel, Field


class MessageTopic(str, Enum):
    DISCOVERY = "discovery"
    HEARTBEAT = "heartbeat"
    COMMAND = "command"
    TELEMETRY = "telemetry"


class MeshMessage(BaseModel):
    msg_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: str
    destination: str | None = None  # None = broadcast
    topic: MessageTopic
    payload: dict = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)
    signature: str | None = None
