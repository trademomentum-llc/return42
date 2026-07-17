import pytest
from return42.cliniclink.models import PatientHandoff, HandoffStatus
from return42.cliniclink.store import HandoffStore


@pytest.fixture
def store(tmp_path):
    return HandoffStore(tmp_path / "cliniclink.db")


def test_store_create_and_get(store):
    handoff = PatientHandoff(
        handoff_id="ho-001",
        patient_id="p-123",
        ambulance_id="amb-1",
        clinic_id="clinic-a",
        vital_signs={"hr": 90, "bp": "120/80"},
        medications=["aspirin"],
        chief_complaint="chest pain",
        eta_minutes=12,
    )
    store.create(handoff)
    got = store.get("ho-001")
    assert got.patient_id == "p-123"
    assert got.status == HandoffStatus.PENDING


def test_store_list_filters_by_status(store):
    store.create(PatientHandoff(handoff_id="ho-1", patient_id="p-1", ambulance_id="amb-1", clinic_id="c", status=HandoffStatus.PENDING))
    store.create(PatientHandoff(handoff_id="ho-2", patient_id="p-2", ambulance_id="amb-1", clinic_id="c", status=HandoffStatus.ACKNOWLEDGED))
    assert len(store.list(status=HandoffStatus.PENDING)) == 1
    assert len(store.list()) == 2


def test_store_acknowledge(store):
    store.create(PatientHandoff(handoff_id="ho-1", patient_id="p-1", ambulance_id="amb-1", clinic_id="c"))
    ack = store.acknowledge("ho-1")
    assert ack.status == HandoffStatus.ACKNOWLEDGED
    assert ack.acknowledged_at is not None
