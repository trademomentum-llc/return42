import os

import pytest
from fastapi.testclient import TestClient

from return42.cliniclink.api import create_app
from return42.cliniclink.store import HandoffStore
from return42.observability.telemetry import TelemetryBus


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CLINIC_TOKEN", "test-token")
    monkeypatch.setenv("CLINICLINK_ADMIN_TOKEN", "admin-token")
    monkeypatch.setenv("TRUST_ON_FIRST_USE", "true")
    db = tmp_path / "api.db"
    queue_db = tmp_path / "queue.db"
    app = create_app(db_path=str(db), queue_db_path=str(queue_db))
    return TestClient(app)


def _auth_headers(token="test-token"):
    return {"Authorization": f"Bearer {token}"}


def _admin_headers(token="admin-token"):
    return {"Authorization": f"Bearer {token}"}


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_submit_handoff(client):
    payload = {
        "handoff_id": "ho-api-1",
        "patient_id": "p-1",
        "ambulance_id": "amb-1",
        "clinic_id": "clinic-a",
        "chief_complaint": "chest pain",
        "eta_minutes": 10,
    }
    r = client.post("/handoffs", json=payload, headers=_admin_headers())
    assert r.status_code == 201
    assert r.json()["status"] == "pending"


def test_submit_handoff_requires_admin_token(client):
    payload = {
        "handoff_id": "ho-api-unauth-submit",
        "patient_id": "p-1",
        "ambulance_id": "amb-1",
        "clinic_id": "clinic-a",
    }
    r = client.post("/handoffs", json=payload)
    assert r.status_code == 403
    # The read/ack token must not allow HTTP submission.
    r = client.post("/handoffs", json=payload, headers=_auth_headers("test-token"))
    assert r.status_code == 403


def test_list_and_ack_handoff(client):
    payload = {
        "handoff_id": "ho-api-2",
        "patient_id": "p-2",
        "ambulance_id": "amb-1",
        "clinic_id": "clinic-a",
    }
    client.post("/handoffs", json=payload, headers=_admin_headers())
    r = client.post("/handoffs/ho-api-2/ack", headers=_auth_headers())
    assert r.status_code == 200
    assert r.json()["status"] == "acknowledged"


def test_list_handoffs_requires_token(client):
    r = client.get("/handoffs")
    assert r.status_code == 403


def test_get_handoff_requires_token(client):
    r = client.get("/handoffs/ho-api-1")
    assert r.status_code == 403


def test_ack_handoff_requires_valid_token(client):
    r = client.post("/handoffs/ho-api-1/ack", headers=_auth_headers("wrong-token"))
    assert r.status_code == 403


def test_duplicate_handoff_id_is_idempotent(client):
    payload = {
        "handoff_id": "ho-dup",
        "patient_id": "p-dup",
        "ambulance_id": "amb-1",
        "clinic_id": "clinic-a",
        "chief_complaint": "chest pain",
        "eta_minutes": 5,
    }
    r1 = client.post("/handoffs", json=payload, headers=_admin_headers())
    assert r1.status_code == 201
    r2 = client.post("/handoffs", json=payload, headers=_admin_headers())
    assert r2.status_code == 201
    assert r2.json()["handoff_id"] == "ho-dup"


def test_duplicate_handoff_id_with_different_contents_fails(client):
    base = {
        "handoff_id": "ho-dup-conflict",
        "patient_id": "p-dup",
        "ambulance_id": "amb-1",
        "clinic_id": "clinic-a",
        "chief_complaint": "chest pain",
        "eta_minutes": 5,
    }
    client.post("/handoffs", json=base, headers=_admin_headers())
    conflict = dict(base)
    conflict["chief_complaint"] = "abdominal pain"
    r = client.post("/handoffs", json=conflict, headers=_admin_headers())
    assert r.status_code == 409


def test_invalid_payload_returns_422(client):
    r = client.post("/handoffs", json={"handoff_id": "bad"}, headers=_admin_headers())
    assert r.status_code == 422


def test_submit_handoff_rejects_wrong_clinic_id(client):
    payload = {
        "handoff_id": "ho-wrong-clinic",
        "patient_id": "p-1",
        "ambulance_id": "amb-1",
        "clinic_id": "clinic-b",
    }
    r = client.post("/handoffs", json=payload, headers=_admin_headers())
    assert r.status_code == 400


def test_submit_handoff_emits_received_telemetry(tmp_path, monkeypatch):
    monkeypatch.setenv("CLINIC_TOKEN", "test-token")
    monkeypatch.setenv("CLINICLINK_ADMIN_TOKEN", "admin-token")
    telemetry = TelemetryBus()
    db = tmp_path / "api.db"
    queue_db = tmp_path / "queue.db"
    app = create_app(
        db_path=str(db), queue_db_path=str(queue_db), telemetry_bus=telemetry, node_id="clinic-a"
    )
    client = TestClient(app)
    payload = {
        "handoff_id": "ho-telemetry",
        "patient_id": "p-1",
        "ambulance_id": "amb-1",
        "clinic_id": "clinic-a",
    }
    r = client.post("/handoffs", json=payload, headers=_admin_headers())
    assert r.status_code == 201
    received = telemetry.events("cliniclink.handoff.received")
    assert any(e.payload.get("handoff_id") == "ho-telemetry" for e in received)


def test_submit_handoff_admin_token_fallback_to_clinic_token(tmp_path, monkeypatch):
    monkeypatch.delenv("CLINICLINK_ADMIN_TOKEN", raising=False)
    monkeypatch.setenv("CLINIC_TOKEN", "shared-token")
    db = tmp_path / "api.db"
    queue_db = tmp_path / "queue.db"
    app = create_app(db_path=str(db), queue_db_path=str(queue_db), node_id="clinic-a")
    client = TestClient(app)
    payload = {
        "handoff_id": "ho-fallback",
        "patient_id": "p-1",
        "ambulance_id": "amb-1",
        "clinic_id": "clinic-a",
    }
    r = client.post("/handoffs", json=payload, headers={"Authorization": "Bearer shared-token"})
    assert r.status_code == 201
