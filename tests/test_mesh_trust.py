"""Tests for the mesh TrustStore."""

import pytest

from return42.mesh.trust import TrustLevel, TrustStore


def test_trust_store_rejects_unknown_when_tofu_off():
    store = TrustStore(tofu=False)
    assert store.is_trusted("som-b") is False
    store.trust_from_discovery("som-b", "key-b64")
    assert store.is_trusted("som-b") is False


def test_trust_store_accepts_pre_enrolled_peer():
    store = TrustStore(tofu=False, trusted_peers={"som-b": "key-b64"})
    assert store.is_trusted("som-b") is True


def test_trust_store_tofu():
    store = TrustStore(tofu=True)
    store.trust_from_discovery("som-b", "key-b64")
    assert store.is_trusted("som-b") is True


def test_trust_store_register_adds_peer():
    store = TrustStore(tofu=False)
    store.register("som-b", "key-b64")
    assert store.is_trusted("som-b") is True


def test_trust_store_from_env_pre_enrolled(monkeypatch):
    monkeypatch.setenv("TRUSTED_PEERS", "som-b:key-b64, som-c:key-c64")
    monkeypatch.setenv("TRUST_ON_FIRST_USE", "false")
    store = TrustStore.from_env()
    assert store.is_trusted("som-b") is True
    assert store.is_trusted("som-c") is True
    assert store.is_trusted("som-d") is False


def test_trust_store_from_env_tofu(monkeypatch):
    monkeypatch.setenv("TRUST_ON_FIRST_USE", "true")
    monkeypatch.delenv("TRUSTED_PEERS", raising=False)
    store = TrustStore.from_env()
    assert store.is_trusted("som-b") is False
    assert store.trust_from_discovery("som-b", "key-b64") is True
    assert store.is_trusted("som-b") is True


def test_trust_level_enum_values():
    assert TrustLevel.UNTRUSTED == "untrusted"
    assert TrustLevel.TRUSTED == "trusted"
