import base64
import os

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from return42.mesh.identity import NodeIdentity


def _signing_key_b64(node: NodeIdentity) -> str:
    """Serialize a node's private key to URL-safe base64."""
    return NodeIdentity._serialize_key_pair(node.signing_key)[1]


def test_node_identity_creation():
    node = NodeIdentity(node_id="som-01")
    assert node.node_id == "som-01"
    assert node.verify_key_b64 is not None
    assert node.public_key == node.verify_key_b64


def test_node_identity_from_env(monkeypatch):
    monkeypatch.setenv("NODE_ID", "som-02")
    node = NodeIdentity.from_env()
    assert node.node_id == "som-02"


def test_identity_sign_and_verify():
    node = NodeIdentity.generate("som-a")
    data = b"hello mesh"
    sig = node.sign(data)
    assert node.verify(data, sig) is True
    assert node.verify(b"tampered", sig) is False


def test_identity_from_env(monkeypatch):
    node = NodeIdentity.generate("som-a")
    monkeypatch.setenv("NODE_SIGNING_KEY", _signing_key_b64(node))
    loaded = NodeIdentity.from_env("som-a")
    assert loaded.verify_key_b64 == node.verify_key_b64


def test_identity_from_env_persists_ephemeral_key(monkeypatch):
    monkeypatch.delenv("NODE_SIGNING_KEY", raising=False)
    identity = NodeIdentity.from_env("som-a", persist_ephemeral=True)
    assert os.environ["NODE_SIGNING_KEY"] == _signing_key_b64(identity)
    reloaded = NodeIdentity.from_env("som-a", persist_ephemeral=True)
    assert _signing_key_b64(reloaded) == _signing_key_b64(identity)
    assert reloaded.verify_key_b64 == identity.verify_key_b64


def test_identity_from_env_does_not_persist_ephemeral_key(monkeypatch):
    monkeypatch.delenv("NODE_SIGNING_KEY", raising=False)
    identity = NodeIdentity.from_env("som-a", persist_ephemeral=False)
    assert "NODE_SIGNING_KEY" not in os.environ
    assert identity.node_id == "som-a"


def test_identity_from_env_default_does_not_persist(monkeypatch):
    monkeypatch.delenv("NODE_SIGNING_KEY", raising=False)
    NodeIdentity.from_env("som-a")
    assert "NODE_SIGNING_KEY" not in os.environ


def test_identity_generate_invalid_seed_length():
    with pytest.raises(ValueError, match="32 bytes"):
        NodeIdentity.generate("som-a", seed=b"too-short")


def test_identity_key_types_and_serialization():
    node = NodeIdentity.generate("som-b")
    assert isinstance(node.signing_key, Ed25519PrivateKey)
    assert isinstance(node.verify_key, Ed25519PublicKey)
    assert isinstance(node.verify_key_b64, str)
    # URL-safe base64 decodes to 32 bytes for the private key and 32 for public.
    assert len(base64.urlsafe_b64decode(_signing_key_b64(node))) == 32
    assert len(base64.urlsafe_b64decode(node.verify_key_b64)) == 32


def test_identity_from_env_malformed(monkeypatch):
    monkeypatch.setenv("NODE_SIGNING_KEY", "not-valid-base64!!!")
    with pytest.raises(ValueError, match="NODE_SIGNING_KEY"):
        NodeIdentity.from_env("som-c")


def test_reconstructed_identity_cannot_sign():
    """Value-equal reconstructed identities must not share the private key cache."""
    original = NodeIdentity.generate("som-a")
    reconstructed = NodeIdentity(
        node_id=original.node_id, verify_key_b64=original.verify_key_b64
    )

    assert original.signing_key is not None
    assert original != reconstructed
    with pytest.raises(RuntimeError, match="private signing key"):
        reconstructed.signing_key
    with pytest.raises(RuntimeError, match="private signing key"):
        reconstructed.sign(b"data")


def test_public_only_identity_verifies_after_original_goes_out_of_scope():
    """A public-only identity can verify signatures after the original dies."""
    verify_key_b64: str
    signature: bytes

    def _create_and_sign() -> tuple[str, bytes]:
        original = NodeIdentity.generate("som-a")
        data = b"hello mesh"
        sig = original.sign(data)
        assert original.verify(data, sig) is True
        return original.verify_key_b64, sig

    verify_key_b64, signature = _create_and_sign()

    public_only = NodeIdentity(node_id="som-a", verify_key_b64=verify_key_b64)
    assert public_only.verify(b"hello mesh", signature) is True
    assert public_only.verify(b"tampered", signature) is False
