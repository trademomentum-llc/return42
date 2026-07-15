from datetime import datetime, timezone

from fastapi.testclient import TestClient

from return42.observability.api import create_app
from return42.observability.telemetry import EventLevel, TelemetryEvent


def test_event_to_evidence_flow(tmp_path):
    app = create_app(log_dir=str(tmp_path))
    client = TestClient(app)

    event = TelemetryEvent(
        name="integration.test",
        source="test-suite",
        level=EventLevel.INFO,
        payload={"status": "green"},
    )
    response = client.post("/events", json=event.model_dump(mode="json"))
    assert response.status_code == 202

    # Evidence log should contain the event. The logger uses a UTC date stamp.
    date_stamp = datetime.fromtimestamp(event.timestamp, tz=timezone.utc).strftime("%Y-%m-%d")
    log_path = tmp_path / f"evidence-{date_stamp}.jsonl"
    files = list(tmp_path.glob("evidence-*.jsonl"))
    assert len(files) == 1
    assert files[0] == log_path
    content = files[0].read_text()
    assert '"integration.test"' in content


def test_dev_metrics_endpoint():
    app = create_app()
    client = TestClient(app)
    response = client.post("/dev-metrics")
    assert response.status_code == 202
    assert response.json()["status"] == "collected"
