"""Append-only JSONL evidence logger."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .telemetry import TelemetryEvent


class EvidenceLogger:
    """Writes telemetry events to append-only JSONL files."""

    def __init__(self, log_dir: str | None = None) -> None:
        self._log_dir = Path(log_dir or os.getenv("EVIDENCE_LOG_DIR", "evidence"))
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._path = self._log_dir / f"evidence-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl"

    @property
    def path(self) -> str:
        return str(self._path)

    def write(self, event: TelemetryEvent) -> None:
        with self._path.open("a", encoding="utf-8") as f:
            f.write(event.model_dump_json() + "\n")
            f.flush()

    def rotate(self) -> None:
        """Start a new daily log file."""
        self._path = self._log_dir / f"evidence-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl"

    def read_lines(self, since: float | None = None) -> list[dict]:
        events = []
        if not self._path.exists():
            return events
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                if since is None or data.get("timestamp", 0) >= since:
                    events.append(data)
        return events
