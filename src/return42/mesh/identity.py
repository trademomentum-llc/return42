"""Mesh node identity with Ed25519 signing keys."""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass, field

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


@dataclass(frozen=True)
class NodeIdentity:
    """A mesh node's identity backed by an Ed25519 key pair.

    The private key is stored only inside the frozen instance so that it can be
    cached as a property; the public/verify key is exposed directly.
    """

    node_id: str
    verify_key_b64: str = ""
    _signing_key_b64: str = field(default="", repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.verify_key_b64 or not self._signing_key_b64:
            signing_key = Ed25519PrivateKey.generate()
            verify_key_b64, signing_key_b64 = self._serialize_key_pair(signing_key)
            object.__setattr__(self, "verify_key_b64", verify_key_b64)
            object.__setattr__(self, "_signing_key_b64", signing_key_b64)

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
        cached = getattr(self, "_cached_signing_key", None)
        if cached is not None:
            return cached
        signing_bytes = base64.urlsafe_b64decode(self._signing_key_b64)
        key = Ed25519PrivateKey.from_private_bytes(signing_bytes)
        object.__setattr__(self, "_cached_signing_key", key)
        return key

    @property
    def signing_key_b64(self) -> str:
        """URL-safe base64 encoding of the private key."""
        return self._signing_key_b64

    @property
    def verify_key(self) -> Ed25519PublicKey:
        """The cached Ed25519 public key derived from the private key."""
        cached = getattr(self, "_cached_verify_key", None)
        if cached is not None:
            return cached
        key = self.signing_key.public_key()
        object.__setattr__(self, "_cached_verify_key", key)
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
        if seed is not None:
            signing_key = Ed25519PrivateKey.from_private_bytes(seed)
        else:
            signing_key = Ed25519PrivateKey.generate()
        verify_key_b64, signing_key_b64 = cls._serialize_key_pair(signing_key)
        return cls(
            node_id=node_id,
            verify_key_b64=verify_key_b64,
            _signing_key_b64=signing_key_b64,
        )

    @classmethod
    def from_env(cls, node_id: str | None = None) -> "NodeIdentity":
        """Load a node identity from the environment.

        ``NODE_SIGNING_KEY`` is expected to be a URL-safe base64 encoded Ed25519
        private key. If it is missing, an ephemeral identity is generated. If it
        is malformed, a clear :class:`ValueError` is raised.
        """
        signing_key_b64 = os.getenv("NODE_SIGNING_KEY")
        resolved_node_id = node_id or os.getenv("NODE_ID", "anonymous")

        if signing_key_b64 is None:
            identity = cls.generate(resolved_node_id)
            os.environ["NODE_SIGNING_KEY"] = identity.signing_key_b64
            return identity

        try:
            signing_bytes = base64.urlsafe_b64decode(signing_key_b64)
            signing_key = Ed25519PrivateKey.from_private_bytes(signing_bytes)
        except Exception as exc:
            raise ValueError("NODE_SIGNING_KEY is malformed") from exc

        verify_key_b64, _ = cls._serialize_key_pair(signing_key)
        return cls(
            node_id=resolved_node_id,
            verify_key_b64=verify_key_b64,
            _signing_key_b64=signing_key_b64,
        )
