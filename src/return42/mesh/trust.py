"""Return42 mesh trust primitives."""

from __future__ import annotations

import os
from enum import Enum


class TrustLevel(str, Enum):
    UNTRUSTED = "untrusted"
    TRUSTED = "trusted"


class TrustStore:
    def __init__(self, tofu: bool = False, trusted_peers: dict[str, str] | None = None) -> None:
        self._tofu = tofu
        self._trusted: dict[str, str] = dict(trusted_peers or {})

    @property
    def is_tofu(self) -> bool:
        return self._tofu

    @property
    def trusted_count(self) -> int:
        return len(self._trusted)

    def is_trusted(self, node_id: str) -> bool:
        return node_id in self._trusted

    def get_key(self, node_id: str) -> str | None:
        """Return the stored verify key for ``node_id`` or ``None``."""
        return self._trusted.get(node_id)

    def register(self, node_id: str, verify_key_b64: str) -> None:
        self._trusted[node_id] = verify_key_b64

    def trust_from_discovery(self, node_id: str, verify_key_b64: str) -> bool:
        if self._tofu:
            self.register(node_id, verify_key_b64)
            return True
        return node_id in self._trusted

    @classmethod
    def from_env(cls) -> "TrustStore":
        tofu = os.getenv("TRUST_ON_FIRST_USE", "false").lower() in ("1", "true", "yes")
        raw = os.getenv("TRUSTED_PEERS", "")
        peers: dict[str, str] = {}
        for entry in raw.split(","):
            entry = entry.strip()
            if not entry:
                continue
            node_id, key = entry.split(":", 1)
            peers[node_id.strip()] = key.strip()
        return cls(tofu=tofu, trusted_peers=peers)
