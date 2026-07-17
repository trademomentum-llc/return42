from __future__ import annotations

from return42.mesh.controller import MessageTopic, SmeshController
from return42.mesh.identity import NodeIdentity
from return42.mesh.transport import MeshTransport
from return42.mesh.trust import TrustStore

from .models import PatientHandoff
from .queue import SyncQueue
from .store import HandoffStore


class ClinicGatewayController:
    """Clinic-side mesh listener that persists inbound patient handoffs."""

    def __init__(
        self,
        identity: NodeIdentity,
        transport: MeshTransport,
        db_path: str,
        queue_db_path: str,
        trust_store: TrustStore | None = None,
    ) -> None:
        self._identity = identity
        self._store = HandoffStore(db_path)
        self._queue = SyncQueue(queue_db_path)
        self._controller = SmeshController(
            identity,
            transport,
            heartbeat_interval=0.05,
            trust_store=trust_store or TrustStore(tofu=True),
        )
        self._controller.on_message(MessageTopic.COMMAND, self._on_handoff)

    @property
    def controller(self) -> SmeshController:
        return self._controller

    @property
    def store(self) -> HandoffStore:
        return self._store

    @property
    def queue(self) -> SyncQueue:
        return self._queue

    async def start(self) -> None:
        await self._controller.start()

    async def stop(self) -> None:
        await self._controller.stop()

    async def _on_handoff(self, msg) -> None:
        payload = msg.payload
        if payload.get("clinic_id") != self._identity.node_id:
            return
        try:
            handoff = PatientHandoff.from_payload(payload)
        except Exception:
            return
        self._store.create(handoff)
        self._queue.enqueue(handoff, "inbound")
