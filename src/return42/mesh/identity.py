"""Mesh node identity."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field


@dataclass(frozen=True)
class NodeIdentity:
    node_id: str
    public_key: str = field(default_factory=lambda: secrets.token_hex(16))
    private_key: str | None = None

    @classmethod
    def from_env(cls) -> "NodeIdentity":
        node_id = os.getenv("NODE_ID", "anonymous")
        return cls(
            node_id=node_id,
            public_key=os.getenv("NODE_PUBLIC_KEY", secrets.token_hex(16)),
            private_key=os.getenv("NODE_PRIVATE_KEY"),
        )

    @classmethod
    def generate(cls, node_id: str) -> "NodeIdentity":
        return cls(
            node_id=node_id,
            public_key=secrets.token_hex(16),
            private_key=secrets.token_hex(32),
        )
