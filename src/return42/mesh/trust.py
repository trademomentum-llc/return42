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
        self._known: dict[str, str] = dict(trusted_peers or {})
        self._trusted: set[str] = set(self._known.keys())

    @property
    def is_tofu(self) -> bool:
        return self._tofu

    @property
    def trusted_count(self) -> int:
        return len(self._trusted)

    @property
    def trusted_peers(self) -> dict[str, str]:
        """Return a copy of the pre-enrolled trusted peer map."""
        return {node_id: self._known[node_id] for node_id in self._trusted}

    def is_trusted(self, node_id: str) -> bool:
        return node_id in self._trusted

    def get_key(self, node_id: str) -> str | None:
        """Return the stored verify key for ``node_id`` or ``None``."""
        return self._known.get(node_id)

    def register(self, node_id: str, verify_key_b64: str) -> None:
        self._known[node_id] = verify_key_b64
        self._trusted.add(node_id)

    def trust_from_discovery(self, node_id: str, verify_key_b64: str) -> bool:
        # Never overwrite a pinned or previously discovered key via discovery.
        if node_id not in self._known:
            self._known[node_id] = verify_key_b64
        if self._tofu or node_id in self._trusted:
            self._trusted.add(node_id)
            return True
        return False

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
