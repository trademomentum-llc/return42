from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from return42.cliniclink.desktop_sidecar.app import create_sidecar_app


@pytest.fixture
def client(tmp_path):
    app = create_sidecar_app()
    app.state.sidecar_db = str(tmp_path / "cliniclink.db")
    app.state.sidecar_queue_db = str(tmp_path / "cliniclink_queue.db")
    return TestClient(app)


def _receive_json_with_timeout(ws, timeout=1.0):
    """Read a JSON message from a TestClient WebSocket with a timeout.

    The local starlette TestClient WebSocket session does not accept a
    ``timeout`` argument on ``receive_json``, so we wrap the blocking call
    in a thread and bail out if nothing arrives.
    """
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(ws.receive_json)
        return future.result(timeout=timeout)
    except TimeoutError:
        raise TimeoutError("no websocket message within timeout")
    finally:
        executor.shutdown(wait=False)


def test_websocket_events(client):
    with client.websocket_connect("/events") as ws:
        # Trigger an event by changing mode via HTTP
        client.post("/mode", json={"mode": "clinic"})
        messages = []
        # Read at most 5 messages with timeout
        for _ in range(5):
            try:
                messages.append(_receive_json_with_timeout(ws, timeout=1.0))
            except Exception:
                break
        assert any(m["type"] == "mode.changed" for m in messages)
