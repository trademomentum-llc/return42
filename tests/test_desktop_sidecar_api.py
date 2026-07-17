import pytest
from fastapi.testclient import TestClient
from return42.cliniclink.desktop_sidecar.app import create_sidecar_app


@pytest.fixture
def client(tmp_path):
    app = create_sidecar_app()
    app.state.sidecar_db = str(tmp_path / "cliniclink.db")
    app.state.sidecar_queue_db = str(tmp_path / "cliniclink_queue.db")
    with TestClient(app) as client:
        yield client


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_get_mode(client):
    r = client.get("/mode")
    assert r.status_code == 200
    assert r.json()["mode"] is None


def test_clinic_handoff_flow(client, tmp_path, monkeypatch):
    monkeypatch.setenv("CLINIC_TOKEN", "clinic-token")
    monkeypatch.setenv("CLINICLINK_ADMIN_TOKEN", "admin-token")

    # Set clinic mode
    r = client.post("/mode", json={"mode": "clinic"})
    assert r.status_code == 200

    # Create a handoff in the fixture's db path (simulating ambulance delivery)
    from return42.cliniclink.models import PatientHandoff
    from return42.cliniclink.store import HandoffStore
    store = HandoffStore(client.app.state.sidecar_db)
    store.create(PatientHandoff(handoff_id="ho-1", patient_id="p-1", ambulance_id="amb-1", clinic_id="clinic-a"))

    r = client.get("/clinic/handoffs", headers={"Authorization": "Bearer clinic-token"})
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.post("/clinic/handoffs/ho-1/ack", headers={"Authorization": "Bearer clinic-token"})
    assert r.status_code == 200
    assert r.json()["status"] == "acknowledged"


def test_clinic_handoffs_invalid_token(client, monkeypatch):
    monkeypatch.setenv("CLINIC_TOKEN", "clinic-token")
    r = client.get("/clinic/handoffs", headers={"Authorization": "Bearer wrong-token"})
    assert r.status_code == 403


def test_clinic_handoff_missing(client, monkeypatch):
    monkeypatch.setenv("CLINIC_TOKEN", "clinic-token")
    r = client.get("/clinic/handoffs/missing-id", headers={"Authorization": "Bearer clinic-token"})
    assert r.status_code == 404

    r = client.post("/clinic/handoffs/missing-id/ack", headers={"Authorization": "Bearer clinic-token"})
    assert r.status_code == 404


def test_clinic_handoffs_missing_auth(client, monkeypatch):
    monkeypatch.setenv("CLINIC_TOKEN", "clinic-token")
    r = client.get("/clinic/handoffs")
    assert r.status_code == 422
