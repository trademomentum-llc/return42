# Return42

Return42 is a resilient edge communication system built around local-first
networking between XIAO SOM nodes, with an optional NUC gateway bridge for
WAN/SIP capabilities.

This repository contains the `return42` Python package, including the
`return42.observability` subpackage that provides telemetry, evidence logging,
metrics, and API foundations for the suite.

## Observability Suite

### Quick start

```bash
python -m pip install -e ".[dev]"
pytest -q
r42-observe emit-event mesh.heartbeat --source som-01 --payload '{"rssi": -42}'
r42-observe dev-metrics
r42-observe serve
```

### Docker Compose

```bash
python scripts/run_observability_suite.py
```

Open Grafana at http://localhost:3000 (admin/admin) and Prometheus at http://localhost:9090.

### Endpoints

- `GET /health` — service health
- `GET /metrics` — Prometheus exposition
- `POST /events` — ingest telemetry event
- `POST /dev-metrics` — collect git/test/coverage metrics

## Phase 1: Local Mesh Baseline

Run a 3-node sandbox:

```bash
python scripts/run_mesh_sandbox.py
```

Run a single node via CLI:

```bash
r42-observe mesh-node --node-id som-01 --transport memory
```

Mesh events received on all mesh topics are converted to telemetry events and written to the evidence log. See `docs/superpowers/plans/OBSERVABILITY_RUNBOOK.md` for Phase 1 MQTT limitations.
