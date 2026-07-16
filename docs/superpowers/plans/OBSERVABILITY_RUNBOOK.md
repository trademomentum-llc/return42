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

Mesh events received on all mesh topics are converted to telemetry events and written to the evidence log.

### Phase 1 MQTT limitations

- **Shared topics for directed messages.** Directed commands are published to the shared `command` topic; every subscriber receives them and filters locally based on the `destination` field. Node-scoped topics are a future improvement to reduce broker bandwidth and payload leakage.
- **No automatic reconnect.** The MQTT transport does not implement reconnect or backoff in this baseline. A broker disconnect stops the receive loop and requires a process restart.

## Phase 2: Trust and Authentication

Each mesh node uses an Ed25519 signing key pair. Messages are signed before publish and verified on receipt; unsigned or forged messages are dropped. `COMMAND` messages are only dispatched from peers that are trusted. Trust can be established by pre-enrollment (`TRUSTED_PEERS` / `--trusted-peers`) or by opt-in trust-on-first-use (`TRUST_ON_FIRST_USE=1` / `--trust-on-first-use`).

### Generate a node signing key

Generate a key and load it into the current shell environment. The example prints only the public verify key; keep `NODE_SIGNING_KEY` secret.

```bash
export NODE_SIGNING_KEY="$(python - <<'PY'
from return42.mesh.identity import NodeIdentity
import os
identity = NodeIdentity.from_env(persist_ephemeral=True)
print(os.environ["NODE_SIGNING_KEY"])
PY
)"
export NODE_ID=som-01
python - <<'PY'
from return42.mesh.identity import NodeIdentity
print(NodeIdentity.from_env().verify_key_b64)
PY
```

### Run two nodes with pre-shared trust

```bash
# Terminal 1
export NODE_ID=som-01
export NODE_SIGNING_KEY="<som-01-private-key>"
r42-observe mesh-node --node-id som-01 --transport memory

# Terminal 2
export NODE_ID=som-02
export NODE_SIGNING_KEY="<som-02-private-key>"
r42-observe mesh-node \
  --node-id som-02 \
  --transport memory \
  --trusted-peers "som-01:<som-01-verify-key>"
```

For bidirectional command handling, configure `--trusted-peers` on both sides.

### Run the sandbox with trust-on-first-use

```bash
python scripts/run_mesh_sandbox.py --trust-on-first-use
```

TOFU is intended for local sandbox use only.

### Trust and security metrics

The mesh exposes the following Prometheus metrics. The Grafana dashboard at `dashboards/return42-observability.json` includes panels for them.

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `mesh_signature_verifications_total` | counter | `valid=true\|false` | Signature verification attempts |
| `mesh_signature_failures_total` | counter | — | Messages dropped due to invalid signature |
| `mesh_command_rejections_total` | counter | `reason=...` | Commands rejected (e.g., untrusted source) |
| `mesh_peer_trust_state` | gauge | `node_id`, `level=trusted\|untrusted` | Per-peer trust state |

## Extending the suite

- Add new telemetry event handlers in `src/return42/observability/telemetry.py`.
- Register new Prometheus metrics via `MetricsRegistry` in `src/return42/observability/metrics.py`.
- Add new CLI subcommands in `src/return42/observability/cli.py`.
- Update the Grafana dashboard JSON when adding user-facing metrics.
