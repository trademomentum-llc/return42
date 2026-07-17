from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SidecarMode(str, Enum):
    CLINIC = "clinic"
    AMBULANCE = "ambulance"


@dataclass
class SidecarState:
    mode: SidecarMode | None = None
    node_id: str | None = None
    verify_key_b64: str | None = None
    service: object | None = field(default=None, repr=False)


STATE = SidecarState()
