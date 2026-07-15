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
