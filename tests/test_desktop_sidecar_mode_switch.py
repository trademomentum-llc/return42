from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from return42.cliniclink.desktop_sidecar.app import create_sidecar_app
from return42.cliniclink.desktop_sidecar.state import STATE
from return42.cliniclink.desktop_sidecar.websocket import MANAGER


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Isolate this test from other sidecar tests that share global STATE/MANAGER.
    STATE.mode = None
    MANAGER._connections.clear()
    monkeypatch.setenv("CLINIC_TOKEN", "t")
    monkeypatch.setenv("CLINICLINK_ADMIN_TOKEN", "a")
    app = create_sidecar_app()
    app.state.sidecar_db = str(tmp_path / "cliniclink.db")
    app.state.sidecar_queue_db = str(tmp_path / "cliniclink_queue.db")
    with TestClient(app) as client:
        yield client
    STATE.mode = None
    MANAGER._connections.clear()


def _receive_json_with_timeout(ws, timeout=1.0):
    """Read a JSON message from a TestClient WebSocket with a timeout.

    The locally installed starlette TestClient WebSocket session does not
    accept a ``timeout`` argument on ``receive_json``, so we wrap the
    blocking call in a thread and bail out if nothing arrives.
    """
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(ws.receive_json)
        return future.result(timeout=timeout)
    except TimeoutError:
        raise TimeoutError("no websocket message within timeout")
    finally:
        executor.shutdown(wait=False)


def test_mode_switch(client):
    assert client.get("/mode").json()["mode"] is None
    r = client.post("/mode", json={"mode": "clinic"})
    assert r.status_code == 200
    assert client.get("/mode").json()["mode"] == "clinic"
    r = client.post("/mode", json={"mode": "ambulance"})
    assert r.status_code == 200
    assert client.get("/mode").json()["mode"] == "ambulance"


def test_mode_switch_emits_event(client):
    with client.websocket_connect("/events") as ws:
        client.post("/mode", json={"mode": "clinic"})
        messages = []
        for _ in range(5):
            try:
                messages.append(_receive_json_with_timeout(ws, timeout=1.0))
            except Exception:
                break
        assert any(
            m["type"] == "mode.changed" and m["payload"]["mode"] == "clinic"
            for m in messages
        )
