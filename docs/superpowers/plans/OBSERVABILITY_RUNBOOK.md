# Return42 Observability Runbook

This runbook describes how to run, verify, and extend the Return42 observability suite.

## Prerequisites

- Python 3.11 or newer
- Docker and Docker Compose (for the Prometheus/Grafana stack)
- Git

## Install

```bash
python -m pip install -e ".[dev]"
```

## Verify

```bash
pytest -q
```

All tests should pass.

## CLI

The `r42-observe` command is installed by the package.

### Emit a telemetry event

```bash
r42-observe emit-event mesh.heartbeat --source som-01 --payload '{"rssi": -42}'
```

### Collect development metrics

```bash
r42-observe dev-metrics
```

### Start the API server

```bash
r42-observe serve
```

The server listens on `http://0.0.0.0:8000` by default.

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service health |
| GET | `/metrics` | Prometheus exposition |
| POST | `/events` | Ingest telemetry event |
| POST | `/dev-metrics` | Collect git/test/coverage metrics |

## Docker Compose observability stack

```bash
python scripts/run_observability_suite.py
```

This starts Prometheus, Grafana, and the observability API.

- Grafana: http://localhost:3000 (default login `admin/admin`)
- Prometheus: http://localhost:9090

The provisioned Grafana dashboard is located at `dashboards/return42-observability.json`.

## Phase 1: Local Mesh Baseline

Run a 3-node sandbox:

```bash
python scripts/run_mesh_sandbox.py
```

Run a single node via CLI:

```bash
r42-observe mesh-node --node-id som-01 --transport memory
```

Mesh events received on the `command` topic are converted to telemetry events and written to the evidence log.

## Extending the suite

- Add new telemetry event handlers in `src/return42/observability/telemetry.py`.
- Register new Prometheus metrics via `MetricsRegistry` in `src/return42/observability/metrics.py`.
- Add new CLI subcommands in `src/return42/observability/cli.py`.
- Update the Grafana dashboard JSON when adding user-facing metrics.
