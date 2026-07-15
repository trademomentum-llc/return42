import json
import tempfile
from pathlib import Path

from return42.observability.evidence import EvidenceLogger
from return42.observability.telemetry import TelemetryEvent, EventLevel


def test_evidence_logger_appends_jsonl():
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = EvidenceLogger(log_dir=tmpdir)
        event = TelemetryEvent(name="test.event", source="test", level=EventLevel.INFO, payload={"ok": True})
        logger.write(event)
        logger.write(event)

        lines = list(Path(logger.path).read_text().strip().split("\n"))
        assert len(lines) == 2
        for line in lines:
            data = json.loads(line)
            assert data["name"] == "test.event"
            assert data["payload"]["ok"] is True


def test_evidence_logger_uses_env_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("EVIDENCE_LOG_DIR", str(tmp_path))
    logger = EvidenceLogger()
    assert logger.path.startswith(str(tmp_path))
