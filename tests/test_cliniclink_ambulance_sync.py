import pytest
from return42.cliniclink.ambulance_client import AmbulanceSyncClient
from return42.cliniclink.models import PatientHandoff
from return42.mesh.controller import SmeshController
from return42.mesh.identity import NodeIdentity
from return42.mesh.message import MessageTopic
from return42.mesh.transport import InMemoryTransport
from return42.mesh.trust import TrustStore
from tests.conftest import _wait_for


@pytest.mark.asyncio
async def test_ambulance_submits_handoff_to_clinic(tmp_path):
    bus = InMemoryTransport()

    ambulance_id = "amb-1"
    clinic_id = "clinic-a"

    ambulance_identity = NodeIdentity.generate(ambulance_id)
    clinic_identity = NodeIdentity.generate(clinic_id)

    # Clinic trusts the ambulance
    clinic_store = TrustStore(
        tofu=False,
        trusted_peers={ambulance_id: ambulance_identity.verify_key_b64},
    )
    ambulance_store = TrustStore(
        tofu=False,
        trusted_peers={clinic_id: clinic_identity.verify_key_b64},
    )

    db_path = tmp_path / "clinic.db"
    queue_path = tmp_path / "queue.db"

    ambulance = AmbulanceSyncClient(
        identity=ambulance_identity,
        transport=bus,
        clinic_id=clinic_id,
        trust_store=ambulance_store,
    )

    clinic = SmeshController(
        clinic_identity,
        bus,
        heartbeat_interval=0.05,
        trust_store=clinic_store,
    )

    received_handoffs = []

    def on_handoff(msg):
        received_handoffs.append(msg.payload)

    clinic.on_message(MessageTopic.COMMAND, on_handoff)

    await ambulance.start()
    await clinic.start()

    await _wait_for(lambda: len(ambulance.controller.peers) == 1 and len(clinic.peers) == 1)

    handoff = PatientHandoff(
        handoff_id="ho-sync-1",
        patient_id="p-1",
        ambulance_id=ambulance_id,
        clinic_id=clinic_id,
        chief_complaint="chest pain",
        eta_minutes=8,
    )
    await ambulance.submit_handoff(handoff)

    await _wait_for(lambda: len(received_handoffs) == 1)
    assert received_handoffs[0]["handoff_id"] == "ho-sync-1"

    await ambulance.stop()
    await clinic.stop()
