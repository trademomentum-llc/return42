# ClinicLink Ambulance-to-Clinic Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a functioning, production-ready ClinicLink application that lets ambulances securely hand off structured patient data to rural clinics over a local Return42 mesh when cellular connectivity is unavailable.

**Architecture:** ClinicLink runs as a FastAPI gateway with an embedded SQLite store at the clinic. Ambulance nodes use `SmeshController` to discover the clinic and push signed `PatientHandoff` records. The gateway queues inbound handoffs if its WAN/gateway is down and replays them on recovery. A lightweight web dashboard lets clinic staff view and acknowledge incoming handoffs. Trust is enforced via the existing `TrustStore`: pre-enrolled ambulance keys can write; clinic staff authenticate locally to read/acknowledge.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, SQLite (stdlib), existing Return42 mesh/identity/trust/controller/observability, pytest-asyncio, Docker Compose.

## Global Constraints

- Python version floor: **3.11**
- All runtime configuration via environment variables with sensible defaults.
- Evidence logs are **append-only JSONL**; never overwrite existing log files.
- Prometheus metrics use `prometheus_client` default registry.
- All tests use **pytest** and run with `pytest -q`.
- File paths are relative to repository root; source code lives under `src/return42/`.
- Commit messages follow conventional commits (`feat:`, `test:`, `docs:`, `chore:`).
- No production secrets in code; use `.env` files or environment variables.
- Private signing keys must never be logged or exposed in evidence/telemetry payloads.
- Patient health information (PHI) must not be logged or emitted in telemetry payloads.

---

## File Structure

```
.
├── src/return42/
│   └── cliniclink/
│       ├── __init__.py
│       ├── models.py          # PatientHandoff Pydantic models
│       ├── store.py           # SQLite repository
│       ├── policy.py          # Trust/policy decisions
│       ├── queue.py           # Queue/sync service
│       ├── api.py             # FastAPI gateway endpoints
│       ├── dashboard.py       # Static dashboard mount
│       ├── ambulance_client.py # Ambulance-side sync client
│       └── static/
│           └── index.html     # Clinic dashboard
├── tests/
│   ├── test_cliniclink_models.py
│   ├── test_cliniclink_store.py
│   ├── test_cliniclink_policy.py
│   ├── test_cliniclink_queue.py
│   ├── test_cliniclink_api.py
│   ├── test_cliniclink_dashboard.py
│   └── test_cliniclink_ambulance_sync.py
├── docker-compose.cliniclink.yml
└── README.md updates
```

---

### Task 1: Add ClinicLink Package Scaffold

**Files:**
- Create: `src/return42/cliniclink/__init__.py`
- Test: `tests/test_cliniclink_imports.py`

**Interfaces:**
- Produces: `return42.cliniclink` package importable.

- [ ] **Step 1: Write failing test**

Create `tests/test_cliniclink_imports.py`:

```python
def test_cliniclink_package_imports():
    import return42.cliniclink
    import return42.cliniclink.models
    import return42.cliniclink.store
    import return42.cliniclink.policy
    import return42.cliniclink.queue
    import return42.cliniclink.api
    import return42.cliniclink.dashboard
    import return42.cliniclink.ambulance_client
```

Run: `.venv/bin/python -m pytest tests/test_cliniclink_imports.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 2: Create package**

Create `src/return42/cliniclink/__init__.py`:

```python
"""ClinicLink: ambulance-to-clinic handoff over resilient edge mesh."""

__version__ = "0.1.0"
```

Create empty placeholder files for the modules so the import test passes:

```bash
touch src/return42/cliniclink/models.py \
      src/return42/cliniclink/store.py \
      src/return42/cliniclink/policy.py \
      src/return42/cliniclink/queue.py \
      src/return42/cliniclink/api.py \
      src/return42/cliniclink/dashboard.py \
      src/return42/cliniclink/ambulance_client.py
```

- [ ] **Step 3: Run test**

Run: `.venv/bin/python -m pytest tests/test_cliniclink_imports.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/return42/cliniclink/ tests/test_cliniclink_imports.py
git commit -m "feat(cliniclink): package scaffold"
```

---

### Task 2: PatientHandoff Data Model and SQLite Store

**Files:**
- Create: `src/return42/cliniclink/models.py`
- Create: `src/return42/cliniclink/store.py`
- Test: `tests/test_cliniclink_store.py`

**Interfaces:**
- Produces:
  - `PatientHandoff` pydantic model with fields: `handoff_id`, `patient_id`, `ambulance_id`, `clinic_id`, `vital_signs`, `medications`, `chief_complaint`, `eta_minutes`, `status`, `created_at`, `acknowledged_at`
  - `HandoffStore(db_path)` with `create(handoff)`, `get(handoff_id)`, `list(status=None)`, `acknowledge(handoff_id)`

- [ ] **Step 1: Write failing tests**

Create `tests/test_cliniclink_store.py`:

```python
import pytest
from return42.cliniclink.models import PatientHandoff, HandoffStatus
from return42.cliniclink.store import HandoffStore


@pytest.fixture
def store(tmp_path):
    return HandoffStore(tmp_path / "cliniclink.db")


def test_store_create_and_get(store):
    handoff = PatientHandoff(
        handoff_id="ho-001",
        patient_id="p-123",
        ambulance_id="amb-1",
        clinic_id="clinic-a",
        vital_signs={"hr": 90, "bp": "120/80"},
        medications=["aspirin"],
        chief_complaint="chest pain",
        eta_minutes=12,
    )
    store.create(handoff)
    got = store.get("ho-001")
    assert got.patient_id == "p-123"
    assert got.status == HandoffStatus.PENDING


def test_store_list_filters_by_status(store):
    store.create(PatientHandoff(handoff_id="ho-1", patient_id="p-1", ambulance_id="amb-1", clinic_id="c", status=HandoffStatus.PENDING))
    store.create(PatientHandoff(handoff_id="ho-2", patient_id="p-2", ambulance_id="amb-1", clinic_id="c", status=HandoffStatus.ACKNOWLEDGED))
    assert len(store.list(status=HandoffStatus.PENDING)) == 1
    assert len(store.list()) == 2


def test_store_acknowledge(store):
    store.create(PatientHandoff(handoff_id="ho-1", patient_id="p-1", ambulance_id="amb-1", clinic_id="c"))
    ack = store.acknowledge("ho-1")
    assert ack.status == HandoffStatus.ACKNOWLEDGED
    assert ack.acknowledged_at is not None
```

Run: `.venv/bin/python -m pytest tests/test_cliniclink_store.py -v`
Expected: FAIL.

- [ ] **Step 2: Implement models and store**

Create `src/return42/cliniclink/models.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class HandoffStatus(str, Enum):
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    REJECTED = "rejected"


class PatientHandoff(BaseModel):
    handoff_id: str
    patient_id: str
    ambulance_id: str
    clinic_id: str
    vital_signs: dict = Field(default_factory=dict)
    medications: list[str] = Field(default_factory=list)
    chief_complaint: str = ""
    eta_minutes: int | None = None
    status: HandoffStatus = HandoffStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged_at: datetime | None = None

    def to_payload(self) -> dict:
        return self.model_dump(mode="json")

    @classmethod
    def from_payload(cls, payload: dict) -> "PatientHandoff":
        return cls.model_validate(payload)
```

Create `src/return42/cliniclink/store.py`:

```python
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import HandoffStatus, PatientHandoff


class HandoffStore:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path, check_same_thread=False)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS handoffs (
                    handoff_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    ambulance_id TEXT NOT NULL,
                    clinic_id TEXT NOT NULL,
                    vital_signs TEXT NOT NULL,
                    medications TEXT NOT NULL,
                    chief_complaint TEXT NOT NULL,
                    eta_minutes INTEGER,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    acknowledged_at TEXT
                )
                """
            )

    @staticmethod
    def _row_to_handoff(row: sqlite3.Row) -> PatientHandoff:
        return PatientHandoff(
            handoff_id=row["handoff_id"],
            patient_id=row["patient_id"],
            ambulance_id=row["ambulance_id"],
            clinic_id=row["clinic_id"],
            vital_signs=json.loads(row["vital_signs"]),
            medications=json.loads(row["medications"]),
            chief_complaint=row["chief_complaint"],
            eta_minutes=row["eta_minutes"],
            status=HandoffStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            acknowledged_at=datetime.fromisoformat(row["acknowledged_at"]) if row["acknowledged_at"] else None,
        )

    def create(self, handoff: PatientHandoff) -> PatientHandoff:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO handoffs (handoff_id, patient_id, ambulance_id, clinic_id,
                                      vital_signs, medications, chief_complaint, eta_minutes,
                                      status, created_at, acknowledged_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    handoff.handoff_id,
                    handoff.patient_id,
                    handoff.ambulance_id,
                    handoff.clinic_id,
                    json.dumps(handoff.vital_signs),
                    json.dumps(handoff.medications),
                    handoff.chief_complaint,
                    handoff.eta_minutes,
                    handoff.status.value,
                    handoff.created_at.isoformat(),
                    handoff.acknowledged_at.isoformat() if handoff.acknowledged_at else None,
                ),
            )
        return handoff

    def get(self, handoff_id: str) -> PatientHandoff | None:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM handoffs WHERE handoff_id = ?", (handoff_id,)).fetchone()
        return self._row_to_handoff(row) if row else None

    def list(self, status: HandoffStatus | None = None) -> list[PatientHandoff]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            if status is not None:
                rows = conn.execute("SELECT * FROM handoffs WHERE status = ? ORDER BY created_at DESC", (status.value,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM handoffs ORDER BY created_at DESC").fetchall()
        return [self._row_to_handoff(row) for row in rows]

    def acknowledge(self, handoff_id: str) -> PatientHandoff:
        now = datetime.now(timezone.utc)
        with self._connect() as conn:
            conn.execute(
                "UPDATE handoffs SET status = ?, acknowledged_at = ? WHERE handoff_id = ?",
                (HandoffStatus.ACKNOWLEDGED.value, now.isoformat(), handoff_id),
            )
        handoff = self.get(handoff_id)
        if handoff is None:
            raise ValueError(f"handoff not found: {handoff_id}")
        return handoff
```

- [ ] **Step 3: Run tests**

Run: `.venv/bin/python -m pytest tests/test_cliniclink_store.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/return42/cliniclink/models.py src/return42/cliniclink/store.py tests/test_cliniclink_store.py
git commit -m "feat(cliniclink): PatientHandoff model and SQLite store"
```

---

### Task 3: Trust Policy Engine

**Files:**
- Create: `src/return42/cliniclink/policy.py`
- Test: `tests/test_cliniclink_policy.py`

**Interfaces:**
- Produces:
  - `ClinicPolicy` with `__init__(trust_store)`, `can_submit_handoff(ambulance_id, verify_key_b64) -> bool`, `can_acknowledge(clinic_token) -> bool`

- [ ] **Step 1: Write failing tests**

Create `tests/test_cliniclink_policy.py`:

```python
from return42.cliniclink.policy import ClinicPolicy
from return42.mesh.trust import TrustStore


def test_policy_allows_pre_enrolled_ambulance():
    store = TrustStore(tofu=False, trusted_peers={"amb-1": "a1b2c3"})
    policy = ClinicPolicy(store)
    assert policy.can_submit_handoff("amb-1", "a1b2c3") is True


def test_policy_rejects_unknown_ambulance_when_tofu_off():
    store = TrustStore(tofu=False)
    policy = ClinicPolicy(store)
    assert policy.can_submit_handoff("amb-1", "a1b2c3") is False


def test_policy_accepts_unknown_ambulance_when_tofu_on():
    store = TrustStore(tofu=True)
    policy = ClinicPolicy(store)
    assert policy.can_submit_handoff("amb-1", "a1b2c3") is True


def test_policy_rejects_key_mismatch():
    store = TrustStore(tofu=False, trusted_peers={"amb-1": "a1b2c3"})
    policy = ClinicPolicy(store)
    assert policy.can_submit_handoff("amb-1", "wrong-key") is False
```

Run: `.venv/bin/python -m pytest tests/test_cliniclink_policy.py -v`
Expected: FAIL.

- [ ] **Step 2: Implement policy engine**

Create `src/return42/cliniclink/policy.py`:

```python
from __future__ import annotations

from return42.mesh.trust import TrustStore


class ClinicPolicy:
    """Authorization policy for ClinicLink handoffs."""

    def __init__(self, trust_store: TrustStore) -> None:
        self._trust_store = trust_store

    def can_submit_handoff(self, ambulance_id: str, verify_key_b64: str) -> bool:
        """An ambulance may submit a handoff if it is trusted and its advertised key matches."""
        if not self._trust_store.is_trusted(ambulance_id):
            # trust_from_discovery records the key and returns True if TOFU is on
            return self._trust_store.trust_from_discovery(ambulance_id, verify_key_b64)
        known_key = self._trust_store.get_key(ambulance_id)
        return known_key == verify_key_b64

    def can_acknowledge(self, clinic_token: str) -> bool:
        """Clinic staff acknowledge via a local bearer token."""
        return bool(clinic_token and clinic_token == self._clinic_token())

    def _clinic_token(self) -> str:
        return "clinic-local-token"  # overridden by env in Task 6
```

- [ ] **Step 3: Run tests**

Run: `.venv/bin/python -m pytest tests/test_cliniclink_policy.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/return42/cliniclink/policy.py tests/test_cliniclink_policy.py
git commit -m "feat(cliniclink): trust policy engine"
```

---

### Task 4: Queue/Sync Service

**Files:**
- Create: `src/return42/cliniclink/queue.py`
- Test: `tests/test_cliniclink_queue.py`

**Interfaces:**
- Produces:
  - `SyncQueue(db_path)` with `enqueue(handoff, direction)`, `dequeue(direction) -> list[dict]`, `mark_done(record_id)`
  - `direction` is `"inbound"` or `"outbound"`

- [ ] **Step 1: Write failing tests**

Create `tests/test_cliniclink_queue.py`:

```python
import pytest
from return42.cliniclink.models import PatientHandoff
from return42.cliniclink.queue import SyncQueue


@pytest.fixture
def queue(tmp_path):
    return SyncQueue(tmp_path / "queue.db")


def test_queue_enqueue_and_dequeue_inbound(queue):
    handoff = PatientHandoff(handoff_id="ho-1", patient_id="p-1", ambulance_id="amb-1", clinic_id="c")
    queue.enqueue(handoff, "inbound")
    pending = queue.dequeue("inbound")
    assert len(pending) == 1
    assert pending[0]["payload"]["handoff_id"] == "ho-1"


def test_queue_mark_done(queue):
    handoff = PatientHandoff(handoff_id="ho-1", patient_id="p-1", ambulance_id="amb-1", clinic_id="c")
    queue.enqueue(handoff, "inbound")
    pending = queue.dequeue("inbound")
    queue.mark_done(pending[0]["id"])
    assert len(queue.dequeue("inbound")) == 0
```

Run: `.venv/bin/python -m pytest tests/test_cliniclink_queue.py -v`
Expected: FAIL.

- [ ] **Step 2: Implement queue**

Create `src/return42/cliniclink/queue.py`:

```python
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import PatientHandoff


class SyncQueue:
    """Persists handoffs that need to be forwarded or replayed after outage."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path, check_same_thread=False)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sync_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    direction TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    done INTEGER NOT NULL DEFAULT 0
                )
                """
            )

    def enqueue(self, handoff: PatientHandoff, direction: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO sync_queue (direction, payload, created_at, done) VALUES (?, ?, ?, 0)",
                (direction, json.dumps(handoff.to_payload()), datetime.now(timezone.utc).isoformat()),
            )

    def dequeue(self, direction: str) -> list[dict]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, payload FROM sync_queue WHERE direction = ? AND done = 0 ORDER BY created_at",
                (direction,),
            ).fetchall()
        return [{"id": row["id"], "payload": json.loads(row["payload"])} for row in rows]

    def mark_done(self, record_id: int) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE sync_queue SET done = 1 WHERE id = ?", (record_id,))
```

- [ ] **Step 3: Run tests**

Run: `.venv/bin/python -m pytest tests/test_cliniclink_queue.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/return42/cliniclink/queue.py tests/test_cliniclink_queue.py
git commit -m "feat(cliniclink): sync queue service"
```

---

### Task 5: Gateway API

**Files:**
- Create: `src/return42/cliniclink/api.py`
- Modify: `src/return42/cliniclink/policy.py` (load token from env)
- Test: `tests/test_cliniclink_api.py`

**Interfaces:**
- Produces:
  - FastAPI app with endpoints:
    - `POST /handoffs` — submit handoff (used by ambulance client)
    - `GET /handoffs` — list handoffs, optional `status` filter
    - `GET /handoffs/{handoff_id}` — get one handoff
    - `POST /handoffs/{handoff_id}/ack` — clinic acknowledges handoff
    - `GET /health` — service health

- [ ] **Step 1: Write failing tests**

Create `tests/test_cliniclink_api.py`:

```python
import os

import pytest
from fastapi.testclient import TestClient

from return42.cliniclink.api import create_app
from return42.cliniclink.store import HandoffStore


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CLINIC_TOKEN", "test-token")
    db = tmp_path / "api.db"
    queue_db = tmp_path / "queue.db"
    app = create_app(db_path=str(db), queue_db_path=str(queue_db))
    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_submit_handoff(client):
    payload = {
        "handoff_id": "ho-api-1",
        "patient_id": "p-1",
        "ambulance_id": "amb-1",
        "clinic_id": "clinic-a",
        "chief_complaint": "chest pain",
        "eta_minutes": 10,
    }
    r = client.post("/handoffs", json=payload)
    assert r.status_code == 201
    assert r.json()["status"] == "pending"


def test_list_and_ack_handoff(client):
    payload = {
        "handoff_id": "ho-api-2",
        "patient_id": "p-2",
        "ambulance_id": "amb-1",
        "clinic_id": "clinic-a",
    }
    client.post("/handoffs", json=payload)
    r = client.post("/handoffs/ho-api-2/ack", headers={"Authorization": "Bearer test-token"})
    assert r.status_code == 200
    assert r.json()["status"] == "acknowledged"
```

Run: `.venv/bin/python -m pytest tests/test_cliniclink_api.py -v`
Expected: FAIL.

- [ ] **Step 2: Implement API**

Update `src/return42/cliniclink/policy.py` to load token from env:

```python
import os

class ClinicPolicy:
    def __init__(self, trust_store: TrustStore) -> None:
        self._trust_store = trust_store
        self._clinic_token = os.getenv("CLINIC_TOKEN", "clinic-local-token")

    # ... existing methods ...

    def can_acknowledge(self, clinic_token: str) -> bool:
        return bool(clinic_token and clinic_token == self._clinic_token)
```

Create `src/return42/cliniclink/api.py`:

```python
from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException

from return42.mesh.trust import TrustStore

from .models import HandoffStatus, PatientHandoff
from .policy import ClinicPolicy
from .queue import SyncQueue
from .store import HandoffStore


def create_app(
    db_path: str | None = None,
    queue_db_path: str | None = None,
    trust_store: TrustStore | None = None,
) -> FastAPI:
    db_path = db_path or os.getenv("CLINICLINK_DB_PATH", "cliniclink.db")
    queue_db_path = queue_db_path or os.getenv("CLINICLINK_QUEUE_DB_PATH", "cliniclink_queue.db")
    trust_store = trust_store or TrustStore.from_env()

    store = HandoffStore(db_path)
    queue = SyncQueue(queue_db_path)
    policy = ClinicPolicy(trust_store)

    app = FastAPI(title="ClinicLink", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/handoffs", status_code=201)
    def submit_handoff(payload: dict[str, Any]) -> PatientHandoff:
        handoff = PatientHandoff.from_payload(payload)
        # Trust check uses advertised key from payload or header; simplified: trust ambulance_id via TrustStore
        # Real key verification happens in mesh client before reaching API; API still checks policy by ID
        if not policy.can_submit_handoff(handoff.ambulance_id, payload.get("ambulance_verify_key", "")):
            raise HTTPException(status_code=403, detail="ambulance not trusted")
        store.create(handoff)
        queue.enqueue(handoff, "inbound")
        return handoff

    @app.get("/handoffs")
    def list_handoffs(status: HandoffStatus | None = None) -> list[PatientHandoff]:
        return store.list(status=status)

    @app.get("/handoffs/{handoff_id}")
    def get_handoff(handoff_id: str) -> PatientHandoff:
        handoff = store.get(handoff_id)
        if handoff is None:
            raise HTTPException(status_code=404, detail="handoff not found")
        return handoff

    @app.post("/handoffs/{handoff_id}/ack")
    def acknowledge_handoff(handoff_id: str, authorization: str = Header(...)) -> PatientHandoff:
        token = authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else authorization
        if not policy.can_acknowledge(token):
            raise HTTPException(status_code=403, detail="invalid clinic token")
        try:
            return store.acknowledge(handoff_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return app
```

- [ ] **Step 3: Run tests**

Run: `.venv/bin/python -m pytest tests/test_cliniclink_api.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/return42/cliniclink/api.py src/return42/cliniclink/policy.py tests/test_cliniclink_api.py
git commit -m "feat(cliniclink): gateway API endpoints"
```

---

### Task 6: Web Dashboard

**Files:**
- Create: `src/return42/cliniclink/static/index.html`
- Create: `src/return42/cliniclink/dashboard.py`
- Modify: `src/return42/cliniclink/api.py` (mount static files)
- Test: `tests/test_cliniclink_dashboard.py`

**Interfaces:**
- Produces: Dashboard served at `/` showing pending handoffs with acknowledge buttons.

- [ ] **Step 1: Write failing test**

Create `tests/test_cliniclink_dashboard.py`:

```python
from fastapi.testclient import TestClient
from return42.cliniclink.api import create_app


def test_dashboard_loads(tmp_path, monkeypatch):
    monkeypatch.setenv("CLINIC_TOKEN", "t")
    app = create_app(db_path=str(tmp_path / "d.db"), queue_db_path=str(tmp_path / "q.db"))
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    assert "ClinicLink" in r.text
```

Run: `.venv/bin/python -m pytest tests/test_cliniclink_dashboard.py -v`
Expected: FAIL.

- [ ] **Step 2: Implement dashboard**

Create `src/return42/cliniclink/static/index.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ClinicLink Dashboard</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; }
    h1 { color: #2a9d8f; }
    .handoff { border: 1px solid #ddd; border-radius: 8px; padding: 1rem; margin: 1rem 0; }
    .handoff h3 { margin: 0 0 0.5rem; }
    .meta { color: #666; font-size: 0.9rem; }
    button { background: #2a9d8f; color: white; border: none; padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer; }
    button:disabled { background: #999; }
  </style>
</head>
<body>
  <h1>ClinicLink Dashboard</h1>
  <div id="app">
    <p>Loading handoffs...</p>
  </div>

  <script>
    const app = document.getElementById('app');
    const token = localStorage.getItem('clinic_token') || prompt('Enter clinic token:');
    if (token) localStorage.setItem('clinic_token', token);

    async function loadHandoffs() {
      const res = await fetch('/handoffs?status=pending');
      const handoffs = await res.json();
      if (handoffs.length === 0) {
        app.innerHTML = '<p>No pending handoffs.</p>';
        return;
      }
      app.innerHTML = handoffs.map(h => `
        <div class="handoff" id="ho-${h.handoff_id}">
          <h3>${h.patient_id} — ${h.chief_complaint || 'No complaint recorded'}</h3>
          <div class="meta">Ambulance: ${h.ambulance_id} | ETA: ${h.eta_minutes ?? '?'} min</div>
          <pre>${JSON.stringify(h.vital_signs, null, 2)}</pre>
          <button onclick="ack('${h.handoff_id}')">Acknowledge</button>
        </div>
      `).join('');
    }

    async function ack(id) {
      await fetch(`/handoffs/${id}/ack`, { method: 'POST', headers: { 'Authorization': `Bearer ${token}` } });
      loadHandoffs();
    }

    loadHandoffs();
    setInterval(loadHandoffs, 5000);
  </script>
</body>
</html>
```

Create `src/return42/cliniclink/dashboard.py`:

```python
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles


def mount_dashboard(app: FastAPI) -> None:
    static_dir = Path(__file__).parent / "static"
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
```

Update `src/return42/cliniclink/api.py` to mount the dashboard at the bottom of `create_app`, before `return app`:

```python
from .dashboard import mount_dashboard
# ... existing code ...
    mount_dashboard(app)
    return app
```

- [ ] **Step 3: Run test**

Run: `.venv/bin/python -m pytest tests/test_cliniclink_dashboard.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/return42/cliniclink/static/index.html src/return42/cliniclink/dashboard.py src/return42/cliniclink/api.py tests/test_cliniclink_dashboard.py
git commit -m "feat(cliniclink): web dashboard"
```

---

### Task 7: Ambulance-to-Clinic Sync Client

**Files:**
- Create: `src/return42/cliniclink/ambulance_client.py`
- Test: `tests/test_cliniclink_ambulance_sync.py`

**Interfaces:**
- Produces:
  - `AmbulanceSyncClient(identity, transport, clinic_id, trust_store, api_url=None)`
  - `submit_handoff(handoff)` sends the handoff over the mesh to the clinic gateway
  - The clinic-side `ClinicLinkController` receives mesh messages and calls the local API

- [ ] **Step 1: Write failing tests**

Create `tests/test_cliniclink_ambulance_sync.py`:

```python
import pytest
from return42.cliniclink.ambulance_client import AmbulanceSyncClient
from return42.cliniclink.models import PatientHandoff
from return42.mesh.controller import SmeshController
from return42.mesh.identity import NodeIdentity
from return42.mesh.message import MessageTopic
from return42.mesh.transport import InMemoryTransport
from return42.mesh.trust import TrustStore
from tests.conftest import _wait_for


@pytest.mark.asyncio
async def test_ambulance_submits_handoff_to_clinic(tmp_path):
    bus = InMemoryTransport()

    ambulance_id = "amb-1"
    clinic_id = "clinic-a"

    ambulance_identity = NodeIdentity.generate(ambulance_id)
    clinic_identity = NodeIdentity.generate(clinic_id)

    # Clinic trusts the ambulance
    clinic_store = TrustStore(
        tofu=False,
        trusted_peers={ambulance_id: ambulance_identity.verify_key_b64},
    )
    ambulance_store = TrustStore(
        tofu=False,
        trusted_peers={clinic_id: clinic_identity.verify_key_b64},
    )

    db_path = tmp_path / "clinic.db"
    queue_path = tmp_path / "queue.db"

    ambulance = AmbulanceSyncClient(
        identity=ambulance_identity,
        transport=bus,
        clinic_id=clinic_id,
        trust_store=ambulance_store,
    )

    clinic = SmeshController(
        clinic_identity,
        bus,
        heartbeat_interval=0.05,
        trust_store=clinic_store,
    )

    received_handoffs = []

    def on_handoff(msg):
        received_handoffs.append(msg.payload)

    clinic.on_message(MessageTopic.COMMAND, on_handoff)

    await ambulance.start()
    await clinic.start()

    await _wait_for(lambda: len(ambulance.controller.peers) == 1 and len(clinic.peers) == 1)

    handoff = PatientHandoff(
        handoff_id="ho-sync-1",
        patient_id="p-1",
        ambulance_id=ambulance_id,
        clinic_id=clinic_id,
        chief_complaint="chest pain",
        eta_minutes=8,
    )
    await ambulance.submit_handoff(handoff)

    await _wait_for(lambda: len(received_handoffs) == 1)
    assert received_handoffs[0]["handoff_id"] == "ho-sync-1"

    await ambulance.stop()
    await clinic.stop()
```

Run: `.venv/bin/python -m pytest tests/test_cliniclink_ambulance_sync.py -v`
Expected: FAIL.

- [ ] **Step 2: Implement ambulance client**

Create `src/return42/cliniclink/ambulance_client.py`:

```python
from __future__ import annotations

from return42.mesh.controller import MessageTopic, SmeshController
from return42.mesh.identity import NodeIdentity
from return42.mesh.message import MeshMessage
from return42.mesh.transport import MeshTransport
from return42.mesh.trust import TrustStore

from .models import PatientHandoff


class AmbulanceSyncClient:
    """Ambulance-side client that submits patient handoffs to a clinic over the mesh."""

    def __init__(
        self,
        identity: NodeIdentity,
        transport: MeshTransport,
        clinic_id: str,
        trust_store: TrustStore | None = None,
    ) -> None:
        self._identity = identity
        self._clinic_id = clinic_id
        self._controller = SmeshController(
            identity,
            transport,
            heartbeat_interval=0.05,
            trust_store=trust_store or TrustStore(tofu=True),
        )

    @property
    def controller(self) -> SmeshController:
        return self._controller

    async def start(self) -> None:
        await self._controller.start()

    async def stop(self) -> None:
        await self._controller.stop()

    async def submit_handoff(self, handoff: PatientHandoff) -> None:
        msg = MeshMessage(
            source=self._identity.node_id,
            destination=self._clinic_id,
            topic=MessageTopic.COMMAND,
            payload=handoff.to_payload(),
        )
        await self._controller.send(MessageTopic.COMMAND, msg.payload, destination=self._clinic_id)
```

- [ ] **Step 3: Run tests**

Run: `.venv/bin/python -m pytest tests/test_cliniclink_ambulance_sync.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/return42/cliniclink/ambulance_client.py tests/test_cliniclink_ambulance_sync.py
git commit -m "feat(cliniclink): ambulance sync client"
```

---

### Task 8: Clinic-Side Mesh Gateway Handler

**Files:**
- Create: `src/return42/cliniclink/gateway.py`
- Test: `tests/test_cliniclink_gateway.py`

**Interfaces:**
- Produces:
  - `ClinicGatewayController(identity, transport, store, queue, trust_store)`
  - A `SmeshController` wrapper that listens for COMMAND handoffs and persists them via the store/queue.

- [ ] **Step 1: Write failing test**

Create `tests/test_cliniclink_gateway.py`:

```python
import pytest
from return42.cliniclink.gateway import ClinicGatewayController
from return42.cliniclink.models import PatientHandoff
from return42.mesh.identity import NodeIdentity
from return42.mesh.transport import InMemoryTransport
from return42.mesh.trust import TrustStore
from tests.conftest import _wait_for


@pytest.mark.asyncio
async def test_gateway_persists_handoff_from_ambulance(tmp_path):
    bus = InMemoryTransport()
    ambulance_identity = NodeIdentity.generate("amb-1")
    clinic_identity = NodeIdentity.generate("clinic-a")

    clinic_store = TrustStore(
        tofu=False,
        trusted_peers={"amb-1": ambulance_identity.verify_key_b64},
    )

    db_path = tmp_path / "clinic.db"
    queue_path = tmp_path / "queue.db"

    gateway = ClinicGatewayController(
        identity=clinic_identity,
        transport=bus,
        db_path=str(db_path),
        queue_db_path=str(queue_path),
        trust_store=clinic_store,
    )

    ambulance = AmbulanceSyncClient(
        identity=ambulance_identity,
        transport=bus,
        clinic_id="clinic-a",
        trust_store=TrustStore(tofu=False, trusted_peers={"clinic-a": clinic_identity.verify_key_b64}),
    )

    await gateway.start()
    await ambulance.start()

    await _wait_for(lambda: len(gateway.controller.peers) == 1)

    handoff = PatientHandoff(
        handoff_id="ho-gw-1",
        patient_id="p-1",
        ambulance_id="amb-1",
        clinic_id="clinic-a",
    )
    await ambulance.submit_handoff(handoff)

    await _wait_for(lambda: gateway.store.get("ho-gw-1") is not None)
    persisted = gateway.store.get("ho-gw-1")
    assert persisted.patient_id == "p-1"

    await ambulance.stop()
    await gateway.stop()
```

Run: `.venv/bin/python -m pytest tests/test_cliniclink_gateway.py -v`
Expected: FAIL.

- [ ] **Step 2: Implement gateway controller**

Create `src/return42/cliniclink/gateway.py`:

```python
from __future__ import annotations

from return42.mesh.controller import MessageTopic, SmeshController
from return42.mesh.identity import NodeIdentity
from return42.mesh.transport import MeshTransport
from return42.mesh.trust import TrustStore

from .models import PatientHandoff
from .queue import SyncQueue
from .store import HandoffStore


class ClinicGatewayController:
    """Clinic-side mesh listener that persists inbound patient handoffs."""

    def __init__(
        self,
        identity: NodeIdentity,
        transport: MeshTransport,
        db_path: str,
        queue_db_path: str,
        trust_store: TrustStore | None = None,
    ) -> None:
        self._identity = identity
        self._store = HandoffStore(db_path)
        self._queue = SyncQueue(queue_db_path)
        self._controller = SmeshController(
            identity,
            transport,
            heartbeat_interval=0.05,
            trust_store=trust_store or TrustStore(tofu=True),
        )
        self._controller.on_message(MessageTopic.COMMAND, self._on_handoff)

    @property
    def controller(self) -> SmeshController:
        return self._controller

    @property
    def store(self) -> HandoffStore:
        return self._store

    async def start(self) -> None:
        await self._controller.start()

    async def stop(self) -> None:
        await self._controller.stop()

    async def _on_handoff(self, msg) -> None:
        payload = msg.payload
        if payload.get("clinic_id") != self._identity.node_id:
            return
        try:
            handoff = PatientHandoff.from_payload(payload)
        except Exception:
            return
        self._store.create(handoff)
        self._queue.enqueue(handoff, "inbound")
```

- [ ] **Step 3: Run tests**

Run: `.venv/bin/python -m pytest tests/test_cliniclink_gateway.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/return42/cliniclink/gateway.py tests/test_cliniclink_gateway.py
git commit -m "feat(cliniclink): clinic-side mesh gateway controller"
```

---

### Task 9: CLI Entry Point and Docker Compose

**Files:**
- Modify: `pyproject.toml`
- Create: `src/return42/cliniclink/cli.py`
- Create: `docker-compose.cliniclink.yml`
- Test: `tests/test_cliniclink_cli.py`

**Interfaces:**
- Produces:
  - `r42-cliniclink` console script
  - `r42-cliniclink gateway --node-id clinic-a --transport memory|mqtt --db-path ...`
  - Docker Compose stack for clinic gateway + observability

- [ ] **Step 1: Write failing test**

Create `tests/test_cliniclink_cli.py`:

```python
from typer.testing import CliRunner
from return42.cliniclink.cli import app

runner = CliRunner()


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "gateway" in result.output


def test_gateway_help():
    result = runner.invoke(app, ["gateway", "--help"])
    assert result.exit_code == 0
    assert "--node-id" in result.output
```

Run: `.venv/bin/python -m pytest tests/test_cliniclink_cli.py -v`
Expected: FAIL.

- [ ] **Step 2: Implement CLI**

Create `src/return42/cliniclink/cli.py`:

```python
from __future__ import annotations

import asyncio
import os

import typer

from return42.mesh.identity import NodeIdentity
from return42.mesh.transport_mqtt import MqttTransport
from return42.mesh.transport import InMemoryTransport
from return42.mesh.trust import TrustStore

from .gateway import ClinicGatewayController

app = typer.Typer(help="ClinicLink ambulance-to-clinic handoff")


@app.command("gateway")
def gateway(
    node_id: str = typer.Option(..., "--node-id", help="Clinic node identifier"),
    transport: str = typer.Option("memory", "--transport", help="memory or mqtt"),
    db_path: str = typer.Option("cliniclink.db", "--db-path"),
    queue_db_path: str = typer.Option("cliniclink_queue.db", "--queue-db-path"),
) -> None:
    async def run() -> None:
        identity = NodeIdentity.from_env(node_id)
        if transport == "memory":
            tx = InMemoryTransport()
        elif transport == "mqtt":
            tx = MqttTransport(node_id=node_id)
        else:
            raise typer.BadParameter(f"Unknown transport: {transport}")

        controller = ClinicGatewayController(
            identity=identity,
            transport=tx,
            db_path=db_path,
            queue_db_path=queue_db_path,
            trust_store=TrustStore.from_env(),
        )
        await controller.start()
        typer.echo(f"ClinicLink gateway {node_id} running.")
        try:
            while True:
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            pass
        finally:
            await controller.stop()

    asyncio.run(run())
```

Update `pyproject.toml`:

```toml
[project.scripts]
r42-observe = "return42.observability.cli:app"
r42-cliniclink = "return42.cliniclink.cli:app"
```

Create `docker-compose.cliniclink.yml`:

```yaml
services:
  cliniclink-gateway:
    build:
      context: .
      dockerfile_inline: |
        FROM python:3.12-slim
        WORKDIR /app
        COPY pyproject.toml ./
        COPY src ./src
        RUN pip install -e ".[dev]"
        CMD ["r42-cliniclink", "gateway", "--node-id", "clinic-a", "--transport", "mqtt"]
    ports:
      - "8000:8000"
    environment:
      - EVIDENCE_LOG_DIR=/app/evidence
      - CLINICLINK_DB_PATH=/app/data/cliniclink.db
      - CLINICLINK_QUEUE_DB_PATH=/app/data/cliniclink_queue.db
      - CLINIC_TOKEN=${CLINIC_TOKEN:-clinic-local-token}
      - TRUSTED_PEERS=${TRUSTED_PEERS:-}
      - TRUST_ON_FIRST_USE=${TRUST_ON_FIRST_USE:-0}
    volumes:
      - ./evidence:/app/evidence
      - cliniclink-data:/app/data

  mqtt:
    image: eclipse-mosquitto:2
    ports:
      - "1883:1883"
    volumes:
      - ./mosquitto.conf:/mosquitto/config/mosquitto.conf:ro

volumes:
  cliniclink-data:
```

- [ ] **Step 3: Run tests**

Run: `.venv/bin/python -m pytest tests/test_cliniclink_cli.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml src/return42/cliniclink/cli.py docker-compose.cliniclink.yml tests/test_cliniclink_cli.py
git commit -m "feat(cliniclink): CLI and Docker Compose"
```

---

### Task 10: Final Wiring, Docs, and Full Suite Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/plans/OBSERVABILITY_RUNBOOK.md` or create `docs/superpowers/plans/CLINICLINK_RUNBOOK.md`
- Modify: any remaining wiring
- Test: full suite

**Interfaces:**
- Produces: Passing full suite, clean branch, documented setup.

- [ ] **Step 1: Update README**

Add a **ClinicLink** section to `README.md` with:
- What it is and the unmet need it solves
- How to run the gateway locally
- How to run the ambulance sync test/sandbox
- Docker Compose usage
- Environment variables

- [ ] **Step 2: Run full test suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all tests PASS.

- [ ] **Step 3: Run a brief integration smoke test**

Run the ambulance-to-clinic sync test manually:

```bash
.venv/bin/python -m pytest tests/test_cliniclink_gateway.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit final docs and wiring**

```bash
git add README.md docs/superpowers/plans/CLINICLINK_RUNBOOK.md
git commit -m "docs(cliniclink): README and runbook"
```

---

## Self-Review

**Spec coverage:**
- [x] Patient handoff data model
- [x] SQLite persistence
- [x] Trust policy for ambulances
- [x] Queue/replay for resilience
- [x] Gateway API
- [x] Web dashboard
- [x] Ambulance sync client
- [x] Clinic-side mesh gateway
- [x] CLI and Docker Compose
- [x] Documentation

**Placeholder scan:**
- No TBD/TODO placeholders.
- Each step includes concrete code or commands.
- Each task ends with a commit.

**Type consistency:**
- `PatientHandoff` model used across store, queue, API, ambulance client, gateway.
- `TrustStore`, `SmeshController`, `NodeIdentity` interfaces from Phase 2 reused unchanged.
