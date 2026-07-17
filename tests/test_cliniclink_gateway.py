import pytest

from return42.cliniclink.ambulance_client import AmbulanceSyncClient
from return42.cliniclink.gateway import ClinicGatewayController
from return42.cliniclink.models import PatientHandoff
from return42.mesh.controller import MessageTopic, SmeshController
from return42.mesh.identity import NodeIdentity
from return42.mesh.transport import InMemoryTransport
from return42.mesh.trust import TrustStore
from return42.observability.telemetry import TelemetryBus
from tests.conftest import _wait_for


@pytest.mark.asyncio
async def test_gateway_persists_handoff_from_ambulance(tmp_path):
    bus = InMemoryTransport()
    ambulance_identity = NodeIdentity.generate("amb-1")
    clinic_identity = NodeIdentity.generate("clinic-a")

    clinic_store = TrustStore(
        tofu=False,
        trusted_peers={"amb-1": ambulance_identity.verify_key_b64},
    )

    db_path = tmp_path / "clinic.db"
    queue_path = tmp_path / "queue.db"

    gateway = ClinicGatewayController(
        identity=clinic_identity,
        transport=bus,
        db_path=str(db_path),
        queue_db_path=str(queue_path),
        trust_store=clinic_store,
        heartbeat_interval=0.05,
    )

    ambulance = AmbulanceSyncClient(
        identity=ambulance_identity,
        transport=bus,
        clinic_id="clinic-a",
        trust_store=TrustStore(tofu=False, trusted_peers={"clinic-a": clinic_identity.verify_key_b64}),
    )

    await gateway.start()
    await ambulance.start()

    await _wait_for(lambda: len(gateway.controller.peers) == 1)

    handoff = PatientHandoff(
        handoff_id="ho-gw-1",
        patient_id="p-1",
        ambulance_id="amb-1",
        clinic_id="clinic-a",
    )
    await ambulance.submit_handoff(handoff)

    await _wait_for(lambda: gateway.store.get("ho-gw-1") is not None)
    persisted = gateway.store.get("ho-gw-1")
    assert persisted.patient_id == "p-1"

    inbound = gateway.queue.dequeue("inbound")
    assert any(record["payload"]["handoff_id"] == "ho-gw-1" for record in inbound)

    received = gateway.telemetry.events("cliniclink.handoff.received")
    assert any(e.payload.get("handoff_id") == "ho-gw-1" for e in received)

    await ambulance.stop()
    await gateway.stop()


@pytest.mark.asyncio
async def test_gateway_rejects_untrusted_ambulance(tmp_path):
    bus = InMemoryTransport()
    ambulance_identity = NodeIdentity.generate("amb-1")
    clinic_identity = NodeIdentity.generate("clinic-a")

    # Clinic does not trust amb-1
    clinic_store = TrustStore(tofu=False)

    db_path = tmp_path / "clinic.db"
    queue_path = tmp_path / "queue.db"
    telemetry_bus = TelemetryBus()

    gateway = ClinicGatewayController(
        identity=clinic_identity,
        transport=bus,
        db_path=str(db_path),
        queue_db_path=str(queue_path),
        trust_store=clinic_store,
        telemetry_bus=telemetry_bus,
        heartbeat_interval=0.05,
    )

    ambulance = AmbulanceSyncClient(
        identity=ambulance_identity,
        transport=bus,
        clinic_id="clinic-a",
        trust_store=TrustStore(tofu=False, trusted_peers={"clinic-a": clinic_identity.verify_key_b64}),
        heartbeat_interval=0.05,
    )

    await gateway.start()
    await ambulance.start()

    await _wait_for(lambda: len(gateway.controller.peers) == 1)

    handoff = PatientHandoff(
        handoff_id="ho-gw-untrusted",
        patient_id="p-1",
        ambulance_id="amb-1",
        clinic_id="clinic-a",
    )
    await ambulance.submit_handoff(handoff)

    # Give the controller time to reject the command.
    await _wait_for(lambda: len(telemetry_bus.events("mesh.command.rejected")) >= 1, timeout=2.0)

    assert gateway.store.get("ho-gw-untrusted") is None

    await ambulance.stop()
    await gateway.stop()


@pytest.mark.asyncio
async def test_gateway_rejects_wrong_clinic_id(tmp_path):
    bus = InMemoryTransport()
    ambulance_identity = NodeIdentity.generate("amb-1")
    clinic_identity = NodeIdentity.generate("clinic-a")

    clinic_store = TrustStore(
        tofu=False,
        trusted_peers={"amb-1": ambulance_identity.verify_key_b64},
    )

    db_path = tmp_path / "clinic.db"
    queue_path = tmp_path / "queue.db"
    telemetry_bus = TelemetryBus()

    gateway = ClinicGatewayController(
        identity=clinic_identity,
        transport=bus,
        db_path=str(db_path),
        queue_db_path=str(queue_path),
        trust_store=clinic_store,
        telemetry_bus=telemetry_bus,
        heartbeat_interval=0.05,
    )

    ambulance = AmbulanceSyncClient(
        identity=ambulance_identity,
        transport=bus,
        clinic_id="clinic-a",
        trust_store=TrustStore(tofu=False, trusted_peers={"clinic-a": clinic_identity.verify_key_b64}),
        heartbeat_interval=0.05,
    )

    await gateway.start()
    await ambulance.start()

    await _wait_for(lambda: len(gateway.controller.peers) == 1)

    handoff = PatientHandoff(
        handoff_id="ho-gw-wrong-clinic",
        patient_id="p-1",
        ambulance_id="amb-1",
        clinic_id="clinic-b",
    )
    await ambulance.submit_handoff(handoff)

    await _wait_for(
        lambda: any(
            e.payload.get("reason") == "wrong_clinic"
            for e in telemetry_bus.events("cliniclink.handoff.rejected")
        ),
        timeout=2.0,
    )

    assert gateway.store.get("ho-gw-wrong-clinic") is None

    await ambulance.stop()
    await gateway.stop()


@pytest.mark.asyncio
async def test_gateway_rejects_invalid_payload(tmp_path):
    bus = InMemoryTransport()
    ambulance_identity = NodeIdentity.generate("amb-1")
    clinic_identity = NodeIdentity.generate("clinic-a")

    clinic_store = TrustStore(
        tofu=False,
        trusted_peers={"amb-1": ambulance_identity.verify_key_b64},
    )

    db_path = tmp_path / "clinic.db"
    queue_path = tmp_path / "queue.db"
    telemetry_bus = TelemetryBus()

    gateway = ClinicGatewayController(
        identity=clinic_identity,
        transport=bus,
        db_path=str(db_path),
        queue_db_path=str(queue_path),
        trust_store=clinic_store,
        telemetry_bus=telemetry_bus,
        heartbeat_interval=0.05,
    )

    ambulance = SmeshController(
        ambulance_identity,
        bus,
        heartbeat_interval=0.05,
        trust_store=TrustStore(tofu=False, trusted_peers={"clinic-a": clinic_identity.verify_key_b64}),
    )

    await gateway.start()
    await ambulance.start()

    await _wait_for(lambda: len(gateway.controller.peers) == 1)

    await ambulance.send(
        MessageTopic.COMMAND,
        {"clinic_id": "clinic-a", "not_a_handoff": True},
        destination="clinic-a",
    )

    await _wait_for(
        lambda: any(
            e.payload.get("reason") == "invalid_payload"
            for e in telemetry_bus.events("cliniclink.handoff.rejected")
        ),
        timeout=2.0,
    )

    await ambulance.stop()
    await gateway.stop()
