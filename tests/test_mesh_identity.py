import base64
import os

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from return42.mesh.identity import NodeIdentity


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
    monkeypatch.setenv("NODE_SIGNING_KEY", node.signing_key_b64)
    loaded = NodeIdentity.from_env("som-a")
    assert loaded.verify_key_b64 == node.verify_key_b64


def test_identity_from_env_persists_ephemeral_key(monkeypatch):
    monkeypatch.delenv("NODE_SIGNING_KEY", raising=False)
    identity = NodeIdentity.from_env("som-a")
    assert os.environ["NODE_SIGNING_KEY"] == identity.signing_key_b64
    reloaded = NodeIdentity.from_env("som-a")
    assert reloaded.signing_key_b64 == identity.signing_key_b64
    assert reloaded.verify_key_b64 == identity.verify_key_b64


def test_identity_key_types_and_serialization():
    node = NodeIdentity.generate("som-b")
    assert isinstance(node.signing_key, Ed25519PrivateKey)
    assert isinstance(node.verify_key, Ed25519PublicKey)
    assert isinstance(node.signing_key_b64, str)
    assert isinstance(node.verify_key_b64, str)
    # URL-safe base64 decodes to 32 bytes for the private key and 32 for public.
    assert len(base64.urlsafe_b64decode(node.signing_key_b64)) == 32
    assert len(base64.urlsafe_b64decode(node.verify_key_b64)) == 32


def test_identity_from_env_malformed(monkeypatch):
    monkeypatch.setenv("NODE_SIGNING_KEY", "not-valid-base64!!!")
    with pytest.raises(ValueError):
        NodeIdentity.from_env("som-c")
