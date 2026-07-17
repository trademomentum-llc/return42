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
