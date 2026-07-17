# ClinicLink Runbook

This runbook describes how to run, verify, and secure the ClinicLink ambulance-to-clinic handoff application.

## What ClinicLink does

ClinicLink lets ambulances push structured patient handoff records to a rural clinic over the local Return42 mesh when cellular or WAN connectivity is unreliable. The clinic-side gateway persists each handoff in SQLite, queues it for upstream replay if needed, and exposes a web dashboard and REST API so staff can review and acknowledge incoming patients before the ambulance arrives.

## Prerequisites

- Python 3.11 or newer
- Docker and Docker Compose (optional, for the MQTT-based stack)
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

Run the ambulance-to-clinic gateway smoke test:

```bash
python -m pytest tests/test_cliniclink_gateway.py -v
```

## CLI

The `r42-cliniclink` command is installed by the package.

### Run the gateway locally

```bash
export NODE_ID=clinic-a
export CLINIC_TOKEN="$(python -c 'import secrets; print(secrets.token_hex(16))')"
r42-cliniclink gateway --node-id clinic-a --transport memory
```

The gateway serves the dashboard and API at http://localhost:8000 and listens for mesh handoffs.

To use MQTT instead of the in-memory transport:

```bash
r42-cliniclink gateway --node-id clinic-a --transport mqtt
```

### Gateway options

| Option | Default | Description |
|--------|---------|-------------|
| `--node-id` | required | Mesh node identifier |
| `--transport` | `memory` | `memory` or `mqtt` |
| `--db-path` | `cliniclink.db` | SQLite path for handoffs |
| `--queue-db-path` | `cliniclink_queue.db` | SQLite path for sync queue |
| `--api-host` | `0.0.0.0` | HTTP API host |
| `--api-port` | `8000` | HTTP API port |

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service health |
| GET | `/handoffs` | List handoffs, optional `status` filter |
| GET | `/handoffs/{handoff_id}` | Get one handoff |
| POST | `/handoffs` | Submit a new handoff |
| POST | `/handoffs/{handoff_id}/ack` | Acknowledge a handoff (requires `CLINIC_TOKEN`) |

Example handoff submission:

```bash
curl -X POST http://localhost:8000/handoffs \
  -H 'Content-Type: application/json' \
  -d '{
    "handoff_id": "ho-12345",
    "patient_id": "P-12345",
    "ambulance_id": "amb-1",
    "clinic_id": "clinic-a",
    "chief_complaint": "chest pain",
    "eta_minutes": 12,
    "vital_signs": {"hr": 88, "bp": "132/84", "spo2": 97},
    "medications": ["aspirin"]
  }'
```

Example acknowledgement:

```bash
curl -X POST http://localhost:8000/handoffs/ho-12345/ack \
  -H "Authorization: Bearer $CLINIC_TOKEN"
```

## Dashboard

Open http://localhost:8000 in a browser. The dashboard prompts for the clinic token, then polls `/handoffs?status=pending` every five seconds and shows an **Acknowledge** button for each pending handoff.

## Mesh handoff flow

1. The ambulance generates or loads its Ed25519 signing key (`NODE_SIGNING_KEY`).
2. The ambulance discovers the clinic over the mesh and sends a signed `PatientHandoff` to the clinic's node ID.
3. The clinic gateway verifies the ambulance's signature and checks `TrustStore`; unsigned or untrusted messages are dropped.
4. The gateway persists the handoff in `HandoffStore` and enqueues it in `SyncQueue` with direction `inbound`.
5. The dashboard reflects the new pending handoff and clinic staff can acknowledge it.

The `tests/test_cliniclink_gateway.py` integration test exercises this entire flow using the in-memory mesh transport.

## Queue and replay behavior

`SyncQueue` persists handoffs that need to be forwarded or replayed after an outage:

- `enqueue(handoff, direction)` writes a handoff to the queue.
- `dequeue(direction)` returns pending records.
- `mark_done(record_id)` marks a record as processed.

Current inbound handoffs are queued automatically by the gateway and API. Outbound replay can be driven by a background worker that reads `direction="outbound"` records and forwards them to an upstream system once connectivity returns.

## Trust and security

Each mesh node uses an Ed25519 signing key pair. Messages are signed before publish and verified on receipt. The gateway only accepts handoffs from trusted ambulances.

### Generate a node signing key

Run this once per node. It generates a key, loads it into the current shell environment, and prints only the public verify key:

```bash
export NODE_SIGNING_KEY="$(python - <<'PY'
from return42.mesh.identity import NodeIdentity
import os
identity = NodeIdentity.from_env(persist_ephemeral=True)
print(os.environ["NODE_SIGNING_KEY"])
PY
)"
export NODE_ID=amb-1
python - <<'PY'
from return42.mesh.identity import NodeIdentity
print(NodeIdentity.from_env().verify_key_b64)
PY
```

Copy the printed verify key and share it with peers out-of-band. Never share or log the value of `NODE_SIGNING_KEY`.

### Pre-enroll an ambulance at the clinic

```bash
export TRUSTED_PEERS="amb-1:<amb-1-verify-key>"
```

### Trust-on-first-use (sandbox only)

```bash
export TRUST_ON_FIRST_USE=1
```

TOFU is convenient for local development but should not be used in production.

### Clinic staff authentication

Clinic staff authenticate to the acknowledgement endpoint with a bearer token configured by `CLINIC_TOKEN`. Generate a strong token for production:

```bash
export CLINIC_TOKEN="$(python -c 'import secrets; print(secrets.token_hex(32))')"
```

### Security notes

- Private signing keys (`NODE_SIGNING_KEY`) must never be logged, committed, or included in payloads.
- Patient health information (PHI) must not be logged or emitted in telemetry/evidence payloads.
- Use HTTPS or a local mesh link for production deployments; the default HTTP server is intended for local networks.
- Example patient identifiers in documentation and tests use synthetic values such as `P-12345`.

## Docker Compose

Start the ClinicLink stack with an MQTT broker and the gateway:

```bash
docker compose -f docker-compose.cliniclink.yml up --build
```

- Dashboard/API: http://localhost:8000
- MQTT broker: localhost:1883

The compose file uses a named volume `cliniclink-data` for the SQLite databases so handoffs survive container restarts. Pass trust settings and tokens via environment variables or a `.env` file:

```bash
CLINIC_TOKEN="$(python -c 'import secrets; print(secrets.token_hex(32))')"
TRUSTED_PEERS="amb-1:<amb-1-verify-key>"
docker compose -f docker-compose.cliniclink.yml up --build
```

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `NODE_ID` | `anonymous` | Mesh node identifier |
| `NODE_SIGNING_KEY` | *(ephemeral)* | URL-safe base64 Ed25519 private key |
| `TRUSTED_PEERS` | — | Comma-separated `node_id:verify_key_b64` pre-enrolled peers |
| `TRUST_ON_FIRST_USE` | `false` | Auto-trust discovered peers when `1`/`true`/`yes` |
| `CLINIC_TOKEN` | `clinic-local-token` | Bearer token for acknowledging handoffs |
| `CLINICLINK_DB_PATH` | `cliniclink.db` | SQLite path for handoffs |
| `CLINICLINK_QUEUE_DB_PATH` | `cliniclink_queue.db` | SQLite path for sync queue |
| `EVIDENCE_LOG_DIR` | `evidence` | Directory for append-only evidence logs |

## Extending ClinicLink

- Add new handoff fields in `src/return42/cliniclink/models.py` and migrate the SQLite schema in `store.py`.
- Add outbound replay logic that reads `SyncQueue.dequeue("outbound")` and marks records done after successful upstream delivery.
- Add new API endpoints in `src/return42/cliniclink/api.py`.
- Update the dashboard HTML in `src/return42/cliniclink/static/index.html` when adding staff-facing features.
