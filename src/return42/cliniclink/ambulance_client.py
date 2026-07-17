from __future__ import annotations

from return42.mesh.controller import SmeshController
from return42.mesh.identity import NodeIdentity
from return42.mesh.message import MeshMessage, MessageTopic
from return42.mesh.transport import MeshTransport
from return42.mesh.trust import TrustStore

from .models import PatientHandoff


class AmbulanceSyncClient:
    """Ambulance-side client that submits patient handoffs to a clinic over the mesh."""

    def __init__(
        self,
        identity: NodeIdentity,
        transport: MeshTransport,
        clinic_id: str,
        trust_store: TrustStore | None = None,
    ) -> None:
        self._identity = identity
        self._clinic_id = clinic_id
        self._controller = SmeshController(
            identity,
            transport,
            heartbeat_interval=0.05,
            trust_store=trust_store or TrustStore(tofu=True),
        )

    @property
    def controller(self) -> SmeshController:
        return self._controller

    async def start(self) -> None:
        await self._controller.start()

    async def stop(self) -> None:
        await self._controller.stop()

    async def submit_handoff(self, handoff: PatientHandoff) -> None:
        msg = MeshMessage(
            source=self._identity.node_id,
            destination=self._clinic_id,
            topic=MessageTopic.COMMAND,
            payload=handoff.to_payload(),
        )
        await self._controller.send(MessageTopic.COMMAND, msg.payload, destination=self._clinic_id)
