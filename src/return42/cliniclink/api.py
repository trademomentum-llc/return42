from __future__ import annotations

import asyncio
import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import ValidationError

from return42.mesh.trust import TrustStore
from return42.observability.telemetry import EventLevel, TelemetryBus, TelemetryEvent

from .dashboard import mount_dashboard
from .models import HandoffStatus, PatientHandoff
from .policy import ClinicPolicy
from .queue import SyncQueue
from .store import HandoffStore


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        return ""
    return authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else authorization


def create_app(
    db_path: str | None = None,
    queue_db_path: str | None = None,
    trust_store: TrustStore | None = None,
    store: HandoffStore | None = None,
    queue: SyncQueue | None = None,
    telemetry_bus: TelemetryBus | None = None,
) -> FastAPI:
    db_path = db_path or os.getenv("CLINICLINK_DB_PATH", "cliniclink.db")
    queue_db_path = queue_db_path or os.getenv("CLINICLINK_QUEUE_DB_PATH", "cliniclink_queue.db")
    trust_store = trust_store or TrustStore.from_env()

    store = store or HandoffStore(db_path)
    queue = queue or SyncQueue(queue_db_path)
    policy = ClinicPolicy(trust_store)
    telemetry = telemetry_bus or TelemetryBus()
    node_id = os.getenv("NODE_ID", "cliniclink")

    def _emit(name: str, payload: dict) -> None:
        telemetry.publish(
            TelemetryEvent(
                name=name,
                source=node_id,
                level=EventLevel.INFO,
                payload=payload,
            )
        )

    app = FastAPI(title="ClinicLink", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    def _require_clinic_token(authorization: str | None) -> None:
        token = _bearer_token(authorization)
        if not policy.can_acknowledge(token):
            raise HTTPException(status_code=403, detail="invalid clinic token")

    @app.post("/handoffs", status_code=201)
    async def submit_handoff(
        payload: dict[str, Any], authorization: str | None = Header(default=None)
    ) -> PatientHandoff:
        # HTTP submit is restricted to local staff/admin holding the clinic token.
        # The mesh path via ClinicGatewayController is the production-signed path.
        _require_clinic_token(authorization)
        try:
            handoff = PatientHandoff.from_payload(payload)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors()) from exc
        try:
            await asyncio.to_thread(store.create, handoff)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        await asyncio.to_thread(queue.enqueue, handoff, "inbound")
        return handoff

    @app.get("/handoffs")
    async def list_handoffs(
        status: HandoffStatus | None = None, authorization: str | None = Header(default=None)
    ) -> list[PatientHandoff]:
        _require_clinic_token(authorization)
        return await asyncio.to_thread(store.list, status=status)

    @app.get("/handoffs/{handoff_id}")
    async def get_handoff(
        handoff_id: str, authorization: str | None = Header(default=None)
    ) -> PatientHandoff:
        _require_clinic_token(authorization)
        handoff = await asyncio.to_thread(store.get, handoff_id)
        if handoff is None:
            raise HTTPException(status_code=404, detail="handoff not found")
        return handoff

    @app.post("/handoffs/{handoff_id}/ack")
    async def acknowledge_handoff(
        handoff_id: str, authorization: str | None = Header(default=None)
    ) -> PatientHandoff:
        token = _bearer_token(authorization)
        if not policy.can_acknowledge(token):
            raise HTTPException(status_code=403, detail="invalid clinic token")
        try:
            handoff = await asyncio.to_thread(store.acknowledge, handoff_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        _emit(
            "cliniclink.handoff.acknowledged",
            {"handoff_id": handoff_id, "success": True},
        )
        return handoff

    mount_dashboard(app)
    return app
