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

## Phase 2: Trust and Authentication

Each mesh node uses an Ed25519 signing key pair. The private key is loaded from `NODE_SIGNING_KEY` (URL-safe base64); the public verify key is advertised in discovery messages and used to authenticate every incoming message.

### Generate a node signing key

Run this once per node in the terminal where the node will run. It generates a key, exports it to the shell environment, and prints only the public verify key:

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

Copy the printed verify key and share it with peers out-of-band. Never share or log the value of `NODE_SIGNING_KEY`.

### Run two nodes with pre-shared trust

Start the first node after generating its key, then start the second node with `--trusted-peers` set to the first node's verify key:

```bash
# Terminal 1 (som-01)
export NODE_ID=som-01
export NODE_SIGNING_KEY="<som-01-private-key>"
r42-observe mesh-node --node-id som-01 --transport memory

# Terminal 2 (som-02)
export NODE_ID=som-02
export NODE_SIGNING_KEY="<som-02-private-key>"
r42-observe mesh-node \
  --node-id som-02 \
  --transport memory \
  --trusted-peers "som-01:<som-01-verify-key>"
```

For bidirectional command handling, both nodes must trust each other. Use `TRUSTED_PEERS=som-01:<key>,som-02:<key>` or `--trusted-peers` on each side.

### Run the sandbox with trust-on-first-use

For local development, the sandbox can trust peers on first discovery (TOFU):

```bash
python scripts/run_mesh_sandbox.py --trust-on-first-use
```

TOFU is convenient for sandboxing but should not be used in production.
