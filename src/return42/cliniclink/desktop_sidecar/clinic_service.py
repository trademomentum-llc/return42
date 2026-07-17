from __future__ import annotations

import hmac
import os

from fastapi import APIRouter, Header, HTTPException

from return42.cliniclink.models import HandoffStatus, PatientHandoff
from return42.cliniclink.store import HandoffStore


def require_clinic_token(authorization: str) -> str:
    """Validate the clinic bearer token.

    This helper is invoked as a plain function from route handlers, so
    ``authorization`` is a resolved string rather than a FastAPI dependency.
    """
    token = authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else authorization
    expected = os.getenv("CLINIC_TOKEN", "clinic-local-token")
    if not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=403, detail="invalid clinic token")
    return token


class ClinicService:
    def __init__(self, db_path: str | None = None, queue_db_path: str | None = None) -> None:
        self.db_path = db_path or os.getenv("CLINICLINK_DB_PATH", "cliniclink.db")
        # queue_db_path is retained for API symmetry with AmbulanceService and future
        # sync-queue integration, even though the clinic service currently only reads
        # from the handoff store.
        self.queue_db_path = queue_db_path or os.getenv("CLINICLINK_QUEUE_DB_PATH", "cliniclink_queue.db")
        self.store = HandoffStore(self.db_path)

    def get_router(self) -> APIRouter:
        router = APIRouter()
        store = self.store

        @router.get("/handoffs")
        def list_handoffs(status: HandoffStatus | None = None, token: str = Header(..., alias="Authorization")) -> list[PatientHandoff]:
            require_clinic_token(token)
            return store.list(status=status)

        @router.get("/handoffs/{handoff_id}")
        def get_handoff(handoff_id: str, token: str = Header(..., alias="Authorization")):
            require_clinic_token(token)
            handoff = store.get(handoff_id)
            if handoff is None:
                raise HTTPException(status_code=404, detail="handoff not found")
            return handoff

        @router.post("/handoffs/{handoff_id}/ack")
        def ack_handoff(handoff_id: str, token: str = Header(..., alias="Authorization")):
            require_clinic_token(token)
            if store.get(handoff_id) is None:
                raise HTTPException(status_code=404, detail="handoff not found")
            return store.acknowledge(handoff_id)

        return router
