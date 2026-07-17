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

## ClinicLink: Ambulance-to-Clinic Handoff

ClinicLink lets ambulances securely hand off structured patient data to rural clinics over the local Return42 mesh when cellular connectivity is unavailable or unreliable. The clinic runs a small FastAPI gateway that stores inbound handoffs in SQLite, queues them for replay if upstream connectivity drops, and serves a lightweight dashboard so staff can preview and acknowledge incoming patients before the ambulance arrives.

### Quick start

Install the package and run the full test suite:

```bash
python -m pip install -e ".[dev]"
pytest -q
```

Run the ClinicLink gateway locally with the in-memory mesh transport:

```bash
export NODE_ID=clinic-a
export CLINIC_TOKEN="$(python -c 'import secrets; print(secrets.token_hex(16))')"
r42-cliniclink gateway --node-id clinic-a --transport memory
```

The gateway listens for mesh handoffs and serves the dashboard and API at http://localhost:8000.

### Submit a handoff from an ambulance

In another terminal, generate an ambulance identity and submit a handoff to the clinic:

```bash
export NODE_ID=amb-1
export NODE_SIGNING_KEY="$(python - <<'PY'
from return42.mesh.identity import NodeIdentity
import os
identity = NodeIdentity.from_env(persist_ephemeral=True)
print(os.environ["NODE_SIGNING_KEY"])
PY
)"
python - <<'PY'
import asyncio
from return42.cliniclink.ambulance_client import AmbulanceSyncClient
from return42.cliniclink.models import PatientHandoff
from return42.mesh.identity import NodeIdentity
from return42.mesh.transport import InMemoryTransport
from return42.mesh.trust import TrustStore

async def main():
    bus = InMemoryTransport()
    identity = NodeIdentity.from_env()
    client = AmbulanceSyncClient(identity=identity, transport=bus, clinic_id="clinic-a")
    await client.start()
    handoff = PatientHandoff(
        handoff_id="ho-12345",
        patient_id="P-12345",
        ambulance_id="amb-1",
        clinic_id="clinic-a",
        chief_complaint="chest pain",
        eta_minutes=12,
        vital_signs={"hr": 88, "bp": "132/84", "spo2": 97},
        medications=["aspirin"],
    )
    await client.submit_handoff(handoff)
    print("Handoff submitted")
    await client.stop()

asyncio.run(main())
PY
```

Copy the printed verify key from the ambulance terminal and add it to the clinic's `TRUSTED_PEERS` environment variable so the gateway accepts signed handoffs.

### Run the ambulance sync test

The fastest way to exercise the full ambulance → clinic gateway → store → queue flow is the gateway integration test:

```bash
python -m pytest tests/test_cliniclink_gateway.py -v
```

### Docker Compose

Start the ClinicLink stack, including an MQTT broker and the gateway:

```bash
docker compose -f docker-compose.cliniclink.yml up --build
```

The gateway is available at http://localhost:8000 and the dashboard is served at `/`. Configure trust and tokens with the environment variables below.

### Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `NODE_ID` | `anonymous` | Mesh node identifier for the gateway or ambulance |
| `NODE_SIGNING_KEY` | *(ephemeral)* | URL-safe base64 Ed25519 private key; never log or commit this value |
| `TRUSTED_PEERS` | — | Comma-separated `node_id:verify_key_b64` pre-enrolled peers |
| `TRUST_ON_FIRST_USE` | `false` | Set to `1` or `true` to auto-trust discovered peers (sandbox only) |
| `CLINIC_TOKEN` | `clinic-local-token` | Bearer token used by clinic staff to acknowledge handoffs |
| `CLINICLINK_DB_PATH` | `cliniclink.db` | SQLite path for persisted handoffs |
| `CLINICLINK_QUEUE_DB_PATH` | `cliniclink_queue.db` | SQLite path for the replay/sync queue |
| `EVIDENCE_LOG_DIR` | `evidence` | Directory for append-only evidence logs |

See `docs/superpowers/plans/CLINICLINK_RUNBOOK.md` for the full setup, API reference, and security guidance.
