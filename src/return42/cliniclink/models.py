from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class HandoffStatus(str, Enum):
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    REJECTED = "rejected"


class PatientHandoff(BaseModel):
    handoff_id: str
    patient_id: str
    ambulance_id: str
    clinic_id: str
    vital_signs: dict = Field(default_factory=dict)
    medications: list[str] = Field(default_factory=list)
    chief_complaint: str = ""
    eta_minutes: int | None = None
    status: HandoffStatus = HandoffStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged_at: datetime | None = None

    def to_payload(self) -> dict:
        return self.model_dump(mode="json")

    @classmethod
    def from_payload(cls, payload: dict) -> "PatientHandoff":
        return cls.model_validate(payload)
