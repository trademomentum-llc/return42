from __future__ import annotations

import logging
import os

from return42.mesh.trust import TrustStore

logger = logging.getLogger(__name__)


class ClinicPolicy:
    """Authorization policy for ClinicLink handoffs."""

    def __init__(
        self,
        trust_store: TrustStore,
        clinic_token: str | None = None,
        admin_token: str | None = None,
    ) -> None:
        self._trust_store = trust_store
        self._clinic_token = clinic_token
        self._admin_token = admin_token

    @property
    def clinic_token(self) -> str:
        if self._clinic_token is None:
            self._clinic_token = os.getenv("CLINIC_TOKEN", "clinic-local-token")
        return self._clinic_token

    @property
    def admin_token(self) -> str:
        if self._admin_token is None:
            admin_from_env = os.getenv("CLINICLINK_ADMIN_TOKEN")
            if admin_from_env:
                self._admin_token = admin_from_env
            else:
                self._admin_token = self.clinic_token
                logger.warning(
                    "CLINICLINK_ADMIN_TOKEN not set; falling back to CLINIC_TOKEN. "
                    "Read/write tokens are not separated."
                )
        return self._admin_token

    def can_submit_handoff(self, ambulance_id: str, verify_key_b64: str) -> bool:
        """An ambulance may submit a handoff if it is trusted and its advertised key matches."""
        if not self._trust_store.is_trusted(ambulance_id):
            # trust_from_discovery records the key and returns True if TOFU is on
            return self._trust_store.trust_from_discovery(ambulance_id, verify_key_b64)
        known_key = self._trust_store.get_key(ambulance_id)
        return known_key == verify_key_b64

    def can_read(self, clinic_token: str) -> bool:
        """Clinic staff read handoffs via a local bearer token."""
        return bool(clinic_token and clinic_token == self.clinic_token)

    def can_acknowledge(self, clinic_token: str) -> bool:
        """Clinic staff acknowledge via a local bearer token."""
        return self.can_read(clinic_token)

    def can_submit_http_handoff(self, admin_token: str) -> bool:
        """HTTP handoff submission requires a separate admin token."""
        return bool(admin_token and admin_token == self.admin_token)
