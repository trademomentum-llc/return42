import pytest
from fastapi.testclient import TestClient
from return42.cliniclink.desktop_sidecar.app import create_sidecar_app


@pytest.fixture
def client(tmp_path):
    app = create_sidecar_app()
    app.state.sidecar_db = str(tmp_path / "cliniclink.db")
    app.state.sidecar_queue_db = str(tmp_path / "cliniclink_queue.db")
    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_get_mode(client):
    r = client.get("/mode")
    assert r.status_code == 200
    assert r.json()["mode"] is None
