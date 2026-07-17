import pytest

from return42.cliniclink.policy import ClinicPolicy
from return42.mesh.trust import TrustStore


def test_policy_allows_pre_enrolled_ambulance():
    store = TrustStore(tofu=False, trusted_peers={"amb-1": "a1b2c3"})
    policy = ClinicPolicy(store)
    assert policy.can_submit_handoff("amb-1", "a1b2c3") is True


def test_policy_rejects_unknown_ambulance_when_tofu_off():
    store = TrustStore(tofu=False)
    policy = ClinicPolicy(store)
    assert policy.can_submit_handoff("amb-1", "a1b2c3") is False


def test_policy_accepts_unknown_ambulance_when_tofu_on():
    store = TrustStore(tofu=True)
    policy = ClinicPolicy(store)
    assert policy.can_submit_handoff("amb-1", "a1b2c3") is True


def test_policy_rejects_key_mismatch():
    store = TrustStore(tofu=False, trusted_peers={"amb-1": "a1b2c3"})
    policy = ClinicPolicy(store)
    assert policy.can_submit_handoff("amb-1", "wrong-key") is False


def test_policy_can_read_and_ack_use_clinic_token(monkeypatch):
    monkeypatch.setenv("CLINIC_TOKEN", "clinic-token")
    policy = ClinicPolicy(TrustStore(tofu=True))
    assert policy.can_read("clinic-token") is True
    assert policy.can_acknowledge("clinic-token") is True
    assert policy.can_read("wrong-token") is False
    assert policy.can_acknowledge("wrong-token") is False


def test_policy_can_submit_http_requires_admin_token(monkeypatch):
    monkeypatch.setenv("CLINICLINK_ADMIN_TOKEN", "admin-token")
    monkeypatch.setenv("CLINIC_TOKEN", "clinic-token")
    policy = ClinicPolicy(TrustStore(tofu=True))
    assert policy.can_submit_http_handoff("admin-token") is True
    assert policy.can_submit_http_handoff("clinic-token") is False
    assert policy.can_submit_http_handoff("wrong-token") is False


def test_policy_admin_token_defaults_to_clinic_token_with_warning(monkeypatch, caplog):
    monkeypatch.delenv("CLINICLINK_ADMIN_TOKEN", raising=False)
    monkeypatch.setenv("CLINIC_TOKEN", "clinic-token")
    policy = ClinicPolicy(TrustStore(tofu=True))
    with caplog.at_level("WARNING"):
        assert policy.admin_token == "clinic-token"
        assert policy.can_submit_http_handoff("clinic-token") is True
    assert "CLINICLINK_ADMIN_TOKEN not set" in caplog.text
    assert "not separated" in caplog.text
