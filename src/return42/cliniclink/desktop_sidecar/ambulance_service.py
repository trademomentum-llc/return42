from __future__ import annotations

import hmac
import os

from fastapi import APIRouter, Header, HTTPException

from return42.cliniclink.models import PatientHandoff
from return42.cliniclink.queue import SyncQueue
from return42.cliniclink.store import HandoffStore
from return42.mesh.identity import NodeIdentity
from return42.mesh.transport import InMemoryTransport
from return42.mesh.trust import TrustStore


class AmbulanceService:
    def __init__(self, db_path: str | None = None, queue_db_path: str | None = None) -> None:
        self.db_path = db_path or os.getenv("CLINICLINK_DB_PATH", "cliniclink.db")
        self.queue_db_path = queue_db_path or os.getenv("CLINICLINK_QUEUE_DB_PATH", "cliniclink_queue.db")
        self.store = HandoffStore(self.db_path)
        self.queue = SyncQueue(self.queue_db_path)
        self.transport = InMemoryTransport()
        self.identity = NodeIdentity.from_env()
        self.client = None

    async def start(self) -> None:
        from return42.cliniclink.ambulance_client import AmbulanceSyncClient

        self.trust_store = TrustStore(tofu=True)
        self.client = AmbulanceSyncClient(
            identity=self.identity,
            transport=self.transport,
            clinic_id=os.getenv("TARGET_CLINIC_ID", "clinic-a"),
            trust_store=self.trust_store,
        )
        await self.client.start()

    async def stop(self) -> None:
        if self.client:
            await self.client.stop()

    def get_router(self):
        router = APIRouter()
        admin_token = os.getenv("CLINICLINK_ADMIN_TOKEN", os.getenv("CLINIC_TOKEN", "clinic-local-token"))

        def require_admin(authorization: str) -> None:
            token = authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else authorization
            if not hmac.compare_digest(token, admin_token):
                raise HTTPException(status_code=403, detail="invalid admin token")

        @router.get("/clinics")
        async def list_clinics() -> list[dict]:
            peers = self.client.controller.peers if self.client else set()
            trust_store = self.trust_store if self.client else TrustStore(tofu=True)
            return [
                {"node_id": node_id, "verify_key_b64": trust_store.get_key(node_id) or ""}
                for node_id in peers
            ]

        @router.post("/handoffs", status_code=201)
        async def create_handoff(payload: dict, authorization: str = Header(...)):
            require_admin(authorization)
            payload.setdefault("ambulance_id", os.getenv("AMBULANCE_ID", ""))
            handoff = PatientHandoff(**payload)
            self.store.create(handoff)
            self.queue.enqueue(handoff, "outbound")
            # Attempt immediate send; the handoff remains queued in the outbox
            # regardless of whether the immediate send succeeds.
            try:
                if self.client:
                    await self.client.submit_handoff(handoff)
            except Exception:
                pass
            return handoff.to_payload() | {"status": "queued"}

        @router.get("/outbox")
        async def list_outbox() -> list[dict]:
            return [{"id": item["id"], "payload": item["payload"]} for item in self.queue.dequeue("outbound")]

        return router
