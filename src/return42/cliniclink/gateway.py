from __future__ import annotations

from return42.mesh.controller import MessageTopic, SmeshController
from return42.mesh.identity import NodeIdentity
from return42.mesh.transport import MeshTransport
from return42.mesh.trust import TrustStore
from return42.observability.telemetry import TelemetryBus

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
        store: HandoffStore | None = None,
        queue: SyncQueue | None = None,
        telemetry_bus: TelemetryBus | None = None,
    ) -> None:
        self._identity = identity
        self._store = store or HandoffStore(db_path)
        self._queue = queue or SyncQueue(queue_db_path)
        self._telemetry = telemetry_bus or TelemetryBus()
        self._controller = SmeshController(
            identity,
            transport,
            heartbeat_interval=0.05,
            trust_store=trust_store or TrustStore(tofu=True),
            telemetry_bus=self._telemetry,
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

    @property
    def telemetry(self) -> TelemetryBus:
        return self._telemetry

    async def start(self) -> None:
        await self._controller.start()

    async def stop(self) -> None:
        await self._controller.stop()

    def _emit(self, name: str, payload: dict) -> None:
        from return42.observability.telemetry import EventLevel, TelemetryEvent

        self._telemetry.publish(
            TelemetryEvent(
                name=name,
                source=self._identity.node_id,
                level=EventLevel.INFO,
                payload=payload,
            )
        )

    async def _on_handoff(self, msg) -> None:
        payload = msg.payload
        if payload.get("clinic_id") != self._identity.node_id:
            self._emit(
                "cliniclink.handoff.rejected",
                {
                    "source": msg.source,
                    "topic": msg.topic.value,
                    "reason": "wrong_clinic",
                },
            )
            return
        try:
            handoff = PatientHandoff.from_payload(payload)
        except Exception as exc:
            self._emit(
                "cliniclink.handoff.rejected",
                {
                    "source": msg.source,
                    "topic": msg.topic.value,
                    "reason": "invalid_payload",
                    "error": type(exc).__name__,
                },
            )
            return
        try:
            self._store.create(handoff)
            self._queue.enqueue(handoff, "inbound")
        except Exception as exc:
            self._emit(
                "cliniclink.handoff.rejected",
                {
                    "source": msg.source,
                    "handoff_id": handoff.handoff_id,
                    "topic": msg.topic.value,
                    "reason": "store_failure",
                    "error": type(exc).__name__,
                },
            )
            return
        self._emit(
            "cliniclink.handoff.received",
            {
                "source": msg.source,
                "handoff_id": handoff.handoff_id,
                "topic": msg.topic.value,
                "success": True,
            },
        )
