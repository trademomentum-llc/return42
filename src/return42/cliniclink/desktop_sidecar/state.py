from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SidecarMode(str, Enum):
    CLINIC = "clinic"
    AMBULANCE = "ambulance"


@dataclass
class SidecarState:
    """Mutable runtime state for the desktop sidecar.

    The ``service`` field holds the mode-specific service instance created at
    startup (e.g. a :class:`~return42.cliniclink.desktop_sidecar.clinic_service.ClinicService`).
    It is excluded from ``repr`` to avoid leaking configuration details.
    """

    mode: SidecarMode | None = None
    node_id: str | None = None
    verify_key_b64: str | None = None
    service: object | None = field(default=None, repr=False)


STATE = SidecarState()
