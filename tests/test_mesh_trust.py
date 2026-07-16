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


def test_trust_store_discovery_does_not_overwrite_existing_key():
    store = TrustStore(tofu=True)
    store.trust_from_discovery("som-b", "first-key-b64")
    store.trust_from_discovery("som-b", "attacker-key-b64")
    assert store.get_key("som-b") == "first-key-b64"
    assert store.is_trusted("som-b") is True


def test_trust_store_discovery_does_not_overwrite_pre_enrolled_key():
    store = TrustStore(tofu=False, trusted_peers={"som-b": "enrolled-key-b64"})
    store.trust_from_discovery("som-b", "attacker-key-b64")
    assert store.get_key("som-b") == "enrolled-key-b64"
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



def test_trust_store_get_key_returns_registered_key():
    store = TrustStore(tofu=False, trusted_peers={"som-b": "key-b64"})
    assert store.get_key("som-b") == "key-b64"


def test_trust_store_get_key_returns_none_for_unknown():
    store = TrustStore(tofu=False)
    assert store.get_key("som-b") is None


def test_trust_store_is_tofu_property():
    assert TrustStore(tofu=True).is_tofu is True
    assert TrustStore(tofu=False).is_tofu is False


def test_trust_store_trusted_count_property():
    store = TrustStore(tofu=False, trusted_peers={"som-b": "key-b64", "som-c": "key-c64"})
    assert store.trusted_count == 2
    store.register("som-d", "key-d64")
    assert store.trusted_count == 3
