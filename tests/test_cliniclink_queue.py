import pytest
from return42.cliniclink.models import PatientHandoff
from return42.cliniclink.queue import SyncQueue


@pytest.fixture
def queue(tmp_path):
    return SyncQueue(tmp_path / "queue.db")


def test_queue_enqueue_and_dequeue_inbound(queue):
    handoff = PatientHandoff(handoff_id="ho-1", patient_id="p-1", ambulance_id="amb-1", clinic_id="c")
    queue.enqueue(handoff, "inbound")
    pending = queue.dequeue("inbound")
    assert len(pending) == 1
    assert pending[0]["payload"]["handoff_id"] == "ho-1"


def test_queue_mark_done(queue):
    handoff = PatientHandoff(handoff_id="ho-1", patient_id="p-1", ambulance_id="amb-1", clinic_id="c")
    queue.enqueue(handoff, "inbound")
    pending = queue.dequeue("inbound")
    queue.mark_done(pending[0]["id"])
    assert len(queue.dequeue("inbound")) == 0


def test_queue_enqueue_is_idempotent(queue):
    handoff = PatientHandoff(handoff_id="ho-1", patient_id="p-1", ambulance_id="amb-1", clinic_id="c")
    queue.enqueue(handoff, "inbound")
    queue.enqueue(handoff, "inbound")
    pending = queue.dequeue("inbound")
    assert len(pending) == 1
    assert pending[0]["payload"]["handoff_id"] == "ho-1"
