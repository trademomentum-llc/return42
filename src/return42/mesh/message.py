"""Mesh message schema."""

from __future__ import annotations

import base64
import json
import time
import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from .identity import NodeIdentity


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
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)
    signature: str | None = None

    def _canonical_bytes(self) -> bytes:
        """Return the canonical bytes that are signed or verified.

        The canonical form is JSON containing ``source``, ``destination``,
        ``topic``, ``payload``, ``timestamp`` and ``msg_id`` with sorted keys
        and no whitespace.  The ``signature`` field is intentionally excluded
        so that a message can be verified using its own metadata.
        """
        canonical = {
            "source": self.source,
            "destination": self.destination,
            "topic": self.topic.value if isinstance(self.topic, MessageTopic) else self.topic,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "msg_id": self.msg_id,
        }
        return json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def sign(self, identity: NodeIdentity) -> "MeshMessage":
        """Return a copy of this message signed by ``identity``."""
        signable = self.model_copy(update={"signature": None})
        signature_bytes = identity.sign(signable._canonical_bytes())
        return self.model_copy(update={"signature": base64.urlsafe_b64encode(signature_bytes).decode("ascii")})

    def verify(self, identity: NodeIdentity) -> bool:
        """Return ``True`` if ``identity`` validates this message's signature."""
        if self.signature is None:
            return False
        try:
            signature_bytes = base64.urlsafe_b64decode(self.signature)
        except (ValueError, TypeError):
            return False
        signable = self.model_copy(update={"signature": None})
        return identity.verify(signable._canonical_bytes(), signature_bytes)
