"""Command-line interface for the observability suite."""

from __future__ import annotations

import json
import os

import typer
import uvicorn

from .api import create_app
from .dev_collector import DevelopmentCollector
from .evidence import EvidenceLogger
from .telemetry import EventLevel, TelemetryEvent

app = typer.Typer(help="Return42 observability CLI")


@app.command()
def emit_event(
    name: str,
    source: str = "cli",
    level: EventLevel = EventLevel.INFO,
    payload: str = "{}",
    log_dir: str = os.getenv("EVIDENCE_LOG_DIR", "evidence"),
):
    """Emit a telemetry event and write it to evidence log."""
    logger = EvidenceLogger(log_dir=log_dir)
    event = TelemetryEvent(
        name=name,
        source=source,
        level=level,
        payload=json.loads(payload),
    )
    logger.write(event)
    typer.echo("Event accepted")


@app.command()
def dev_metrics(
    coverage_xml: str | None = None,
    repo_path: str = ".",
):
    """Collect and emit development metrics."""
    collector = DevelopmentCollector(repo_path=repo_path)
    collector.emit_all(coverage_xml)
    typer.echo("Development metrics collected")


@app.command()
def serve(
    host: str = "0.0.0.0",
    port: int = 8000,
    log_dir: str = os.getenv("EVIDENCE_LOG_DIR", "evidence"),
):
    """Run the observability API server."""
    api = create_app(log_dir=log_dir)
    uvicorn.run(api, host=host, port=port)


if __name__ == "__main__":
    app()
