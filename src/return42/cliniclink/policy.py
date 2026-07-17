from __future__ import annotations

import os

from return42.mesh.trust import TrustStore


class ClinicPolicy:
    """Authorization policy for ClinicLink handoffs."""

    def __init__(self, trust_store: TrustStore) -> None:
        self._trust_store = trust_store
        self._clinic_token = os.getenv("CLINIC_TOKEN", "clinic-local-token")

    def can_submit_handoff(self, ambulance_id: str, verify_key_b64: str) -> bool:
        """An ambulance may submit a handoff if it is trusted and its advertised key matches."""
        if not self._trust_store.is_trusted(ambulance_id):
            # trust_from_discovery records the key and returns True if TOFU is on
            return self._trust_store.trust_from_discovery(ambulance_id, verify_key_b64)
        known_key = self._trust_store.get_key(ambulance_id)
        return known_key == verify_key_b64

    def can_acknowledge(self, clinic_token: str) -> bool:
        """Clinic staff acknowledge via a local bearer token."""
        return bool(clinic_token and clinic_token == self._clinic_token)
