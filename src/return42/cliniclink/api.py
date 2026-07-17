from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException

from return42.mesh.trust import TrustStore

from .dashboard import mount_dashboard
from .models import HandoffStatus, PatientHandoff
from .policy import ClinicPolicy
from .queue import SyncQueue
from .store import HandoffStore


def create_app(
    db_path: str | None = None,
    queue_db_path: str | None = None,
    trust_store: TrustStore | None = None,
    store: HandoffStore | None = None,
    queue: SyncQueue | None = None,
) -> FastAPI:
    db_path = db_path or os.getenv("CLINICLINK_DB_PATH", "cliniclink.db")
    queue_db_path = queue_db_path or os.getenv("CLINICLINK_QUEUE_DB_PATH", "cliniclink_queue.db")
    trust_store = trust_store or TrustStore.from_env()

    store = store or HandoffStore(db_path)
    queue = queue or SyncQueue(queue_db_path)
    policy = ClinicPolicy(trust_store)

    app = FastAPI(title="ClinicLink", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/handoffs", status_code=201)
    def submit_handoff(payload: dict[str, Any]) -> PatientHandoff:
        handoff = PatientHandoff.from_payload(payload)
        # Trust check uses advertised key from payload or header; simplified: trust ambulance_id via TrustStore
        # Real key verification happens in mesh client before reaching API; API still checks policy by ID
        if not policy.can_submit_handoff(handoff.ambulance_id, payload.get("ambulance_verify_key", "")):
            raise HTTPException(status_code=403, detail="ambulance not trusted")
        store.create(handoff)
        queue.enqueue(handoff, "inbound")
        return handoff

    @app.get("/handoffs")
    def list_handoffs(status: HandoffStatus | None = None) -> list[PatientHandoff]:
        return store.list(status=status)

    @app.get("/handoffs/{handoff_id}")
    def get_handoff(handoff_id: str) -> PatientHandoff:
        handoff = store.get(handoff_id)
        if handoff is None:
            raise HTTPException(status_code=404, detail="handoff not found")
        return handoff

    @app.post("/handoffs/{handoff_id}/ack")
    def acknowledge_handoff(handoff_id: str, authorization: str = Header(...)) -> PatientHandoff:
        token = authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else authorization
        if not policy.can_acknowledge(token):
            raise HTTPException(status_code=403, detail="invalid clinic token")
        try:
            return store.acknowledge(handoff_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    mount_dashboard(app)
    return app
