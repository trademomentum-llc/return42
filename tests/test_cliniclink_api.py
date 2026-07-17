import os

import pytest
from fastapi.testclient import TestClient

from return42.cliniclink.api import create_app
from return42.cliniclink.store import HandoffStore


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CLINIC_TOKEN", "test-token")
    monkeypatch.setenv("TRUST_ON_FIRST_USE", "true")
    db = tmp_path / "api.db"
    queue_db = tmp_path / "queue.db"
    app = create_app(db_path=str(db), queue_db_path=str(queue_db))
    return TestClient(app)


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
    r = client.post("/handoffs", json=payload)
    assert r.status_code == 201
    assert r.json()["status"] == "pending"


def test_list_and_ack_handoff(client):
    payload = {
        "handoff_id": "ho-api-2",
        "patient_id": "p-2",
        "ambulance_id": "amb-1",
        "clinic_id": "clinic-a",
    }
    client.post("/handoffs", json=payload)
    r = client.post("/handoffs/ho-api-2/ack", headers={"Authorization": "Bearer test-token"})
    assert r.status_code == 200
    assert r.json()["status"] == "acknowledged"
