"""FastAPI observability API."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

from .dev_collector import DevelopmentCollector
from .evidence import EvidenceLogger
from .metrics import get_registry
from .telemetry import TelemetryBus, TelemetryEvent


def create_app(log_dir: str | None = None) -> FastAPI:
    log_dir = log_dir or os.getenv("EVIDENCE_LOG_DIR", "evidence")
    app = FastAPI(title="Return42 Observability")
    app.state.bus = TelemetryBus()
    app.state.evidence = EvidenceLogger(log_dir=log_dir)

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "return42-observability"}

    @app.get("/metrics", response_class=PlainTextResponse)
    def metrics():
        return PlainTextResponse(content=get_registry().expose(), media_type="text/plain; version=0.0.4; charset=utf-8")

    @app.post("/events", status_code=202)
    def post_event(event: TelemetryEvent):
        app.state.bus.publish(event)
        app.state.evidence.write(event)
        return {"status": "accepted"}

    @app.post("/dev-metrics", status_code=202)
    def post_dev_metrics(coverage_xml: str | None = None):
        collector = DevelopmentCollector()
        collector.emit_all(coverage_xml)
        return {"status": "collected"}

    return app
