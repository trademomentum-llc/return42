from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import HandoffStatus, PatientHandoff


class HandoffStore:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path, check_same_thread=False)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS handoffs (
                    handoff_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    ambulance_id TEXT NOT NULL,
                    clinic_id TEXT NOT NULL,
                    vital_signs TEXT NOT NULL,
                    medications TEXT NOT NULL,
                    chief_complaint TEXT NOT NULL,
                    eta_minutes INTEGER,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    acknowledged_at TEXT
                )
                """
            )

    @staticmethod
    def _row_to_handoff(row: sqlite3.Row) -> PatientHandoff:
        return PatientHandoff(
            handoff_id=row["handoff_id"],
            patient_id=row["patient_id"],
            ambulance_id=row["ambulance_id"],
            clinic_id=row["clinic_id"],
            vital_signs=json.loads(row["vital_signs"]),
            medications=json.loads(row["medications"]),
            chief_complaint=row["chief_complaint"],
            eta_minutes=row["eta_minutes"],
            status=HandoffStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            acknowledged_at=datetime.fromisoformat(row["acknowledged_at"]) if row["acknowledged_at"] else None,
        )

    @staticmethod
    def _handoff_to_row(handoff: PatientHandoff) -> tuple:
        return (
            handoff.handoff_id,
            handoff.patient_id,
            handoff.ambulance_id,
            handoff.clinic_id,
            json.dumps(handoff.vital_signs),
            json.dumps(handoff.medications),
            handoff.chief_complaint,
            handoff.eta_minutes,
            handoff.status.value,
            handoff.created_at.isoformat(),
            handoff.acknowledged_at.isoformat() if handoff.acknowledged_at else None,
        )

    @staticmethod
    def _same_contents(a: PatientHandoff, b: PatientHandoff) -> bool:
        """Return True if the two handoffs carry identical PHI-bearing content."""
        return (
            a.patient_id == b.patient_id
            and a.ambulance_id == b.ambulance_id
            and a.clinic_id == b.clinic_id
            and a.vital_signs == b.vital_signs
            and a.medications == b.medications
            and a.chief_complaint == b.chief_complaint
            and a.eta_minutes == b.eta_minutes
        )

    def create(self, handoff: PatientHandoff) -> PatientHandoff:
        row = self._handoff_to_row(handoff)
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            conn.execute(
                """
                INSERT INTO handoffs (handoff_id, patient_id, ambulance_id, clinic_id,
                                      vital_signs, medications, chief_complaint, eta_minutes,
                                      status, created_at, acknowledged_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (handoff_id) DO NOTHING
                """,
                row,
            )
            existing = conn.execute(
                "SELECT * FROM handoffs WHERE handoff_id = ?", (handoff.handoff_id,)
            ).fetchone()
        existing_handoff = self._row_to_handoff(existing)
        if not self._same_contents(existing_handoff, handoff):
            raise ValueError(
                f"handoff_id {handoff.handoff_id!r} already exists with different contents"
            )
        return existing_handoff

    def get(self, handoff_id: str) -> PatientHandoff | None:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM handoffs WHERE handoff_id = ?", (handoff_id,)).fetchone()
        return self._row_to_handoff(row) if row else None

    def list(self, status: HandoffStatus | None = None) -> list[PatientHandoff]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            if status is not None:
                rows = conn.execute("SELECT * FROM handoffs WHERE status = ? ORDER BY created_at DESC", (status.value,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM handoffs ORDER BY created_at DESC").fetchall()
        return [self._row_to_handoff(row) for row in rows]

    def acknowledge(self, handoff_id: str) -> PatientHandoff:
        now = datetime.now(timezone.utc)
        with self._connect() as conn:
            conn.execute(
                "UPDATE handoffs SET status = ?, acknowledged_at = ? WHERE handoff_id = ?",
                (HandoffStatus.ACKNOWLEDGED.value, now.isoformat(), handoff_id),
            )
        handoff = self.get(handoff_id)
        if handoff is None:
            raise ValueError(f"handoff not found: {handoff_id}")
        return handoff
