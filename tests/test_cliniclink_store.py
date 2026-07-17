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


def test_store_create_idempotent(store):
    handoff = PatientHandoff(
        handoff_id="ho-dup",
        patient_id="p-1",
        ambulance_id="amb-1",
        clinic_id="clinic-a",
        chief_complaint="chest pain",
        eta_minutes=10,
    )
    first = store.create(handoff)
    second = store.create(handoff)
    assert first.handoff_id == second.handoff_id
    assert first.patient_id == second.patient_id


def test_store_create_conflict_raises(store):
    store.create(
        PatientHandoff(
            handoff_id="ho-conflict",
            patient_id="p-1",
            ambulance_id="amb-1",
            clinic_id="clinic-a",
            chief_complaint="chest pain",
            eta_minutes=10,
        )
    )
    with pytest.raises(ValueError, match="already exists with different contents"):
        store.create(
            PatientHandoff(
                handoff_id="ho-conflict",
                patient_id="p-1",
                ambulance_id="amb-1",
                clinic_id="clinic-a",
                chief_complaint="abdominal pain",
                eta_minutes=10,
            )
        )
