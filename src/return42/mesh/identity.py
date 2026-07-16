"""Mesh node identity with Ed25519 signing keys."""

from __future__ import annotations

import base64
import binascii
import os
import weakref
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


_SIGNING_KEY_CACHE: weakref.WeakKeyDictionary["NodeIdentity", Ed25519PrivateKey] = weakref.WeakKeyDictionary()
_VERIFY_KEY_CACHE: weakref.WeakKeyDictionary["NodeIdentity", Ed25519PublicKey] = weakref.WeakKeyDictionary()


@dataclass(frozen=True)
class NodeIdentity:
    """A mesh node's identity backed by an Ed25519 key pair.

    The public/verify key is carried by the frozen instance; the private
    signing key is stored only in the module-level cache and is not part of
    the serialized identity.
    """

    node_id: str
    verify_key_b64: str = ""

    def __post_init__(self) -> None:
        if not self.verify_key_b64:
            signing_key = Ed25519PrivateKey.generate()
            verify_key_b64, _ = self._serialize_key_pair(signing_key)
            object.__setattr__(self, "verify_key_b64", verify_key_b64)
            _SIGNING_KEY_CACHE[self] = signing_key

    @staticmethod
    def _serialize_key_pair(signing_key: Ed25519PrivateKey) -> tuple[str, str]:
        signing_bytes = signing_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        verify_bytes = signing_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return (
            base64.urlsafe_b64encode(verify_bytes).decode("ascii"),
            base64.urlsafe_b64encode(signing_bytes).decode("ascii"),
        )

    @property
    def public_key(self) -> str:
        """Backward-compatible alias for :attr:`verify_key_b64`."""
        return self.verify_key_b64

    @property
    def signing_key(self) -> Ed25519PrivateKey:
        """The cached Ed25519 private key."""
        cached = _SIGNING_KEY_CACHE.get(self)
        if cached is None:
            raise RuntimeError("private signing key is not available for this identity")
        return cached

    @property
    def verify_key(self) -> Ed25519PublicKey:
        """The cached Ed25519 public key derived from the private key."""
        cached = _VERIFY_KEY_CACHE.get(self)
        if cached is not None:
            return cached
        key = self.signing_key.public_key()
        _VERIFY_KEY_CACHE[self] = key
        return key

    def sign(self, data: bytes) -> bytes:
        """Sign ``data`` and return the raw Ed25519 signature."""
        return self.signing_key.sign(data)

    def verify(self, data: bytes, signature: bytes) -> bool:
        """Return ``True`` if ``signature`` is valid for ``data``."""
        try:
            self.verify_key.verify(signature, data)
            return True
        except InvalidSignature:
            return False

    @classmethod
    def generate(cls, node_id: str, seed: bytes | None = None) -> "NodeIdentity":
        """Generate a new identity, optionally from a deterministic 32-byte seed."""
        if seed is not None and len(seed) != 32:
            raise ValueError("seed must be exactly 32 bytes")
        if seed is not None:
            signing_key = Ed25519PrivateKey.from_private_bytes(seed)
        else:
            signing_key = Ed25519PrivateKey.generate()
        verify_key_b64, _ = cls._serialize_key_pair(signing_key)
        instance = cls(node_id=node_id, verify_key_b64=verify_key_b64)
        _SIGNING_KEY_CACHE[instance] = signing_key
        return instance

    @classmethod
    def from_env(
        cls, node_id: str | None = None, *, persist_ephemeral: bool = False
    ) -> "NodeIdentity":
        """Load a node identity from the environment.

        ``NODE_SIGNING_KEY`` is expected to be a URL-safe base64 encoded Ed25519
        private key. If it is missing, an ephemeral identity is generated. By
        default the ephemeral key is **not** persisted. Persistence should only
        be enabled by passing ``persist_ephemeral=True`` in tests or sandbox
        environments; production callers must leave this disabled so that
        ``os.environ`` is not mutated. If the existing key is malformed, a clear
        :class:`ValueError` is raised.
        """
        signing_key_b64 = os.getenv("NODE_SIGNING_KEY")
        resolved_node_id = node_id or os.getenv("NODE_ID", "anonymous")

        if signing_key_b64 is None:
            identity = cls.generate(resolved_node_id)
            if persist_ephemeral:
                os.environ["NODE_SIGNING_KEY"] = cls._serialize_key_pair(identity.signing_key)[1]
            return identity

        try:
            signing_bytes = base64.urlsafe_b64decode(signing_key_b64)
            signing_key = Ed25519PrivateKey.from_private_bytes(signing_bytes)
        except (binascii.Error, ValueError) as exc:
            raise ValueError(
                "NODE_SIGNING_KEY is malformed: expected URL-safe base64 Ed25519 private key"
            ) from exc

        verify_key_b64, _ = cls._serialize_key_pair(signing_key)
        identity = cls(node_id=resolved_node_id, verify_key_b64=verify_key_b64)
        _SIGNING_KEY_CACHE[identity] = signing_key
        return identity
