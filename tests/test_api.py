from fastapi.testclient import TestClient

from return42.observability.api import create_app
from return42.observability.telemetry import TelemetryEvent, EventLevel


def test_health_endpoint():
    app = create_app()
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_metrics_endpoint():
    app = create_app()
    client = TestClient(app)
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "python_info" in response.text or "# HELP" in response.text


def test_events_endpoint(tmp_path):
    app = create_app(log_dir=str(tmp_path))
    client = TestClient(app)
    event = TelemetryEvent(name="api.test", source="test", level=EventLevel.INFO, payload={"x": 1})
    response = client.post("/events", json=event.model_dump(mode="json"))
    assert response.status_code == 202
