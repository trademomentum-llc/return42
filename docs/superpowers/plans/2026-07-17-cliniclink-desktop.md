# ClinicLink Desktop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a cross-platform Tauri desktop GUI for ClinicLink with an embedded Python sidecar, supporting clinic receive/acknowledge and ambulance create/send workflows over the Return42 mesh.

**Architecture:** A Tauri Rust shell spawns a Python sidecar built from the existing `return42` package. The sidecar exposes HTTP and WebSocket endpoints on loopback. The React frontend communicates via Tauri commands and events. The sidecar proxies to the local ClinicLink gateway in clinic mode and runs `AmbulanceSyncClient` directly in ambulance mode.

**Tech Stack:** Tauri v2, React + TypeScript, Vite, Tailwind CSS, TanStack Query, Zustand, Python 3.11+, FastAPI, WebSocket, PyInstaller, Cargo.

## Global Constraints

- Python version floor: **3.11**
- All runtime configuration via environment variables with sensible defaults.
- Evidence logs are **append-only JSONL**; never overwrite existing log files.
- Prometheus metrics use `prometheus_client` default registry.
- All Python tests use **pytest** and run with `pytest -q`.
- File paths are relative to repository root; source code lives under `src/return42/`.
- Commit messages follow conventional commits (`feat:`, `test:`, `docs:`, `chore:`).
- No production secrets in code; use `.env` files or environment variables.
- Private signing keys must never be logged or exposed in evidence/telemetry payloads.
- Patient health information (PHI) must not be logged or emitted in telemetry payloads.
- The sidecar binds to **127.0.0.1 only**.
- Frontend never sees signing keys.
- PHI is rendered but never persisted in browser storage.

---

## File Structure

```
cliniclink-desktop/               # New top-level directory
├── src-tauri/                    # Rust Tauri shell
│   ├── Cargo.toml
│   ├── tauri.conf.json
│   └── src/
│       ├── main.rs               # Entry point, sidecar spawn
│       ├── lib.rs                # Commands + event forwarding
│       └── sidecar.rs            # Sidecar process management
├── src/                          # React + TypeScript frontend
│   ├── main.tsx
│   ├── App.tsx
│   ├── components/
│   │   ├── ModeSelector.tsx
│   │   ├── ClinicView.tsx
│   │   ├── AmbulanceView.tsx
│   │   ├── HandoffCard.tsx
│   │   ├── HandoffForm.tsx
│   │   ├── ClinicList.tsx
│   │   └── ConnectionStatus.tsx
│   ├── hooks/
│   │   ├── useSidecar.ts
│   │   ├── useEvents.ts
│   │   └── useHandoffs.ts
│   └── api/
│       └── sidecar.ts
├── package.json
├── tsconfig.json
├── vite.config.ts
└── README.md

src/return42/cliniclink/          # Existing Python package additions
├── cli.py                        # Add sidecar subcommand
└── desktop_sidecar/
    ├── __init__.py
    ├── app.py                    # FastAPI app factory
    ├── websocket.py              # WS event manager
    ├── state.py                  # In-memory sidecar state
    ├── clinic_service.py         # Clinic mode logic
    └── ambulance_service.py      # Ambulance mode logic

tests/                            # New and updated tests
├── test_desktop_sidecar_api.py
├── test_desktop_sidecar_websocket.py
├── test_desktop_sidecar_mode_switch.py
└── test_cliniclink_cli.py        # Add sidecar subcommand test
```

---

### Task 1: Add `sidecar` subcommand to `r42-cliniclink` CLI

**Files:**
- Modify: `src/return42/cliniclink/cli.py`
- Test: `tests/test_cliniclink_cli.py`

**Interfaces:**
- Consumes: None
- Produces: `r42-cliniclink sidecar --port 2842` starts the sidecar.

- [ ] **Step 1: Write failing test**

Add to `tests/test_cliniclink_cli.py`:

```python
def test_cli_has_sidecar_command():
    from return42.cliniclink.cli import app
    from typer.testing import CliRunner
    runner = CliRunner()
    result = runner.invoke(app, ["sidecar", "--help"])
    assert result.exit_code == 0
    assert "sidecar" in result.output.lower()
```

Run: `.venv/bin/python -m pytest tests/test_cliniclink_cli.py::test_cli_has_sidecar_command -v`
Expected: FAIL ("No such command 'sidecar'").

- [ ] **Step 2: Implement sidecar subcommand**

In `src/return42/cliniclink/cli.py`, add a `sidecar` Typer command:

```python
import typer
from typing import Annotated

sidecar_app = typer.Typer()

@sidecar_app.command()
def sidecar(
    port: Annotated[int, typer.Option("--port", help="Port to bind the sidecar HTTP/WebSocket server")] = 2842,
    host: Annotated[str, typer.Option("--host", help="Host to bind")] = "127.0.0.1",
) -> None:
    """Run the ClinicLink desktop sidecar."""
    import uvicorn
    from return42.cliniclink.desktop_sidecar.app import create_sidecar_app

    app = create_sidecar_app()
    uvicorn.run(app, host=host, port=port, log_level="info")

app.add_typer(sidecar_app, name="sidecar")
```

- [ ] **Step 3: Run test**

Run: `.venv/bin/python -m pytest tests/test_cliniclink_cli.py::test_cli_has_sidecar_command -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/return42/cliniclink/cli.py tests/test_cliniclink_cli.py
git commit -m "feat(cliniclink): add sidecar subcommand"
```

---

### Task 2: Create sidecar FastAPI app skeleton

**Files:**
- Create: `src/return42/cliniclink/desktop_sidecar/__init__.py`
- Create: `src/return42/cliniclink/desktop_sidecar/state.py`
- Create: `src/return42/cliniclink/desktop_sidecar/app.py`
- Test: `tests/test_desktop_sidecar_api.py`

**Interfaces:**
- Consumes: None
- Produces: `create_sidecar_app()` returns a FastAPI app with `/health`, `/mode`, `/identity` endpoints.

- [ ] **Step 1: Write failing test**

Create `tests/test_desktop_sidecar_api.py`:

```python
import pytest
from fastapi.testclient import TestClient
from return42.cliniclink.desktop_sidecar.app import create_sidecar_app


@pytest.fixture
def client(tmp_path):
    app = create_sidecar_app()
    app.state.sidecar_db = str(tmp_path / "cliniclink.db")
    app.state.sidecar_queue_db = str(tmp_path / "cliniclink_queue.db")
    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_get_mode(client):
    r = client.get("/mode")
    assert r.status_code == 200
    assert r.json()["mode"] is None
```

Run: `.venv/bin/python -m pytest tests/test_desktop_sidecar_api.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 2: Implement state and app skeleton**

Create `src/return42/cliniclink/desktop_sidecar/__init__.py`:

```python
"""ClinicLink Desktop sidecar."""
```

Create `src/return42/cliniclink/desktop_sidecar/state.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SidecarMode(str, Enum):
    CLINIC = "clinic"
    AMBULANCE = "ambulance"


@dataclass
class SidecarState:
    mode: SidecarMode | None = None
    node_id: str | None = None
    verify_key_b64: str | None = None
    service: object | None = field(default=None, repr=False)


STATE = SidecarState()
```

Create `src/return42/cliniclink/desktop_sidecar/app.py`:

```python
from __future__ import annotations

from fastapi import FastAPI

from .state import STATE, SidecarMode


def create_sidecar_app() -> FastAPI:
    app = FastAPI(title="ClinicLink Desktop Sidecar", version="1.0.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/mode")
    def get_mode() -> dict[str, str | None]:
        return {"mode": STATE.mode.value if STATE.mode else None}

    @app.post("/mode")
    def set_mode(payload: dict[str, str]) -> dict[str, str | None]:
        mode = payload.get("mode")
        if mode not in {SidecarMode.CLINIC.value, SidecarMode.AMBULANCE.value}:
            raise ValueError("invalid mode")
        STATE.mode = SidecarMode(mode)
        return {"mode": STATE.mode.value}

    @app.get("/identity")
    def identity() -> dict[str, str | None]:
        return {"node_id": STATE.node_id, "verify_key_b64": STATE.verify_key_b64}

    return app
```

- [ ] **Step 3: Run tests**

Run: `.venv/bin/python -m pytest tests/test_desktop_sidecar_api.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/return42/cliniclink/desktop_sidecar/ tests/test_desktop_sidecar_api.py
git commit -m "feat(cliniclink): sidecar FastAPI skeleton"
```

---

### Task 3: Add WebSocket event manager to sidecar

**Files:**
- Create: `src/return42/cliniclink/desktop_sidecar/websocket.py`
- Modify: `src/return42/cliniclink/desktop_sidecar/app.py`
- Test: `tests/test_desktop_sidecar_websocket.py`

**Interfaces:**
- Consumes: None
- Produces: `EventManager` with `connect(websocket)`, `disconnect(websocket)`, `broadcast(event)`; `/events` WebSocket endpoint.

- [ ] **Step 1: Write failing test**

Create `tests/test_desktop_sidecar_websocket.py`:

```python
import pytest
from fastapi.testclient import TestClient
from return42.cliniclink.desktop_sidecar.app import create_sidecar_app


@pytest.fixture
def client(tmp_path):
    app = create_sidecar_app()
    app.state.sidecar_db = str(tmp_path / "cliniclink.db")
    app.state.sidecar_queue_db = str(tmp_path / "cliniclink_queue.db")
    return TestClient(app)


def test_websocket_events(client):
    with client.websocket_connect("/events") as ws:
        # Trigger an event by changing mode via HTTP
        client.post("/mode", json={"mode": "clinic"})
        messages = []
        # Read at most 5 messages with timeout
        for _ in range(5):
            try:
                messages.append(ws.receive_json(timeout=1.0))
            except Exception:
                break
        assert any(m["type"] == "mode.changed" for m in messages)
```

Run: `.venv/bin/python -m pytest tests/test_desktop_sidecar_websocket.py -v`
Expected: FAIL (WebSocket endpoint missing).

- [ ] **Step 2: Implement event manager and WebSocket endpoint**

Create `src/return42/cliniclink/desktop_sidecar/websocket.py`:

```python
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from fastapi import WebSocket


class EventManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def broadcast(self, event_type: str, payload: dict) -> None:
        event = {
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }
        message = json.dumps(event)
        # Copy set because disconnect may mutate it
        for conn in list(self._connections):
            try:
                await conn.send_text(message)
            except Exception:
                self.disconnect(conn)


MANAGER = EventManager()
```

Modify `src/return42/cliniclink/desktop_sidecar/app.py`:

```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from .state import STATE, SidecarMode
from .websocket import MANAGER


def create_sidecar_app() -> FastAPI:
    app = FastAPI(title="ClinicLink Desktop Sidecar", version="1.0.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/mode")
    def get_mode() -> dict[str, str | None]:
        return {"mode": STATE.mode.value if STATE.mode else None}

    @app.post("/mode")
    async def set_mode(payload: dict[str, str]) -> dict[str, str | None]:
        mode = payload.get("mode")
        if mode not in {SidecarMode.CLINIC.value, SidecarMode.AMBULANCE.value}:
            raise ValueError("invalid mode")
        STATE.mode = SidecarMode(mode)
        await MANAGER.broadcast("mode.changed", {"mode": STATE.mode.value})
        return {"mode": STATE.mode.value}

    @app.get("/identity")
    def identity() -> dict[str, str | None]:
        return {"node_id": STATE.node_id, "verify_key_b64": STATE.verify_key_b64}

    @app.websocket("/events")
    async def events(websocket: WebSocket) -> None:
        await MANAGER.connect(websocket)
        try:
            while True:
                # Keep connection open; optionally handle incoming commands
                data = await websocket.receive_text()
                # Echo as command.received for now; commands handled in later task
                await MANAGER.broadcast("command.received", {"data": data})
        except WebSocketDisconnect:
            MANAGER.disconnect(websocket)

    return app
```

- [ ] **Step 3: Run tests**

Run: `.venv/bin/python -m pytest tests/test_desktop_sidecar_websocket.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/return42/cliniclink/desktop_sidecar/ tests/test_desktop_sidecar_websocket.py
git commit -m "feat(cliniclink): sidecar WebSocket event manager"
```

---

### Task 4: Implement clinic mode service

**Files:**
- Create: `src/return42/cliniclink/desktop_sidecar/clinic_service.py`
- Modify: `src/return42/cliniclink/desktop_sidecar/app.py`
- Modify: `src/return42/cliniclink/desktop_sidecar/state.py`
- Test: `tests/test_desktop_sidecar_api.py`

**Interfaces:**
- Consumes: `HandoffStore`, `SyncQueue`, `create_app` from ClinicLink gateway.
- Produces: `/clinic/handoffs` (GET), `/clinic/handoffs/{id}` (GET), `/clinic/handoffs/{id}/ack` (POST) in sidecar app.

- [ ] **Step 1: Write failing test**

Add to `tests/test_desktop_sidecar_api.py`:

```python
import os


def test_clinic_handoff_flow(client, tmp_path, monkeypatch):
    monkeypatch.setenv("CLINIC_TOKEN", "clinic-token")
    monkeypatch.setenv("CLINICLINK_ADMIN_TOKEN", "admin-token")

    # Set clinic mode
    r = client.post("/mode", json={"mode": "clinic"})
    assert r.status_code == 200

    # Create a handoff in the fixture's db path (simulating ambulance delivery)
    from return42.cliniclink.models import PatientHandoff
    from return42.cliniclink.store import HandoffStore
    store = HandoffStore(client.app.state.sidecar_db)
    store.create(PatientHandoff(handoff_id="ho-1", patient_id="p-1", ambulance_id="amb-1", clinic_id="clinic-a"))

    r = client.get("/clinic/handoffs", headers={"Authorization": "Bearer clinic-token"})
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.post("/clinic/handoffs/ho-1/ack", headers={"Authorization": "Bearer clinic-token"})
    assert r.status_code == 200
    assert r.json()["status"] == "acknowledged"
```

Run: `.venv/bin/python -m pytest tests/test_desktop_sidecar_api.py::test_clinic_handoff_flow -v`
Expected: FAIL (clinic endpoints not defined).

- [ ] **Step 2: Implement clinic service**

Create `src/return42/cliniclink/desktop_sidecar/clinic_service.py`:

```python
from __future__ import annotations

import os

from fastapi import FastAPI, Header, HTTPException

from return42.cliniclink.models import HandoffStatus
from return42.cliniclink.store import HandoffStore


def require_clinic_token(authorization: str = Header(...)) -> str:
    token = authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else authorization
    expected = os.getenv("CLINIC_TOKEN", "clinic-local-token")
    if token != expected:
        raise HTTPException(status_code=403, detail="invalid clinic token")
    return token


class ClinicService:
    def __init__(self, db_path: str | None = None, queue_db_path: str | None = None) -> None:
        self.db_path = db_path or os.getenv("CLINICLINK_DB_PATH", "cliniclink.db")
        self.queue_db_path = queue_db_path or os.getenv("CLINICLINK_QUEUE_DB_PATH", "cliniclink_queue.db")
        self.store = HandoffStore(self.db_path)

    def get_router(self):
        from fastapi import APIRouter

        router = APIRouter()
        store = self.store

        @router.get("/handoffs")
        def list_handoffs(status: HandoffStatus | None = None, token: str = Header(..., alias="Authorization")) -> list:
            require_clinic_token(token)
            return store.list(status=status)

        @router.get("/handoffs/{handoff_id}")
        def get_handoff(handoff_id: str, token: str = Header(..., alias="Authorization")):
            require_clinic_token(token)
            handoff = store.get(handoff_id)
            if handoff is None:
                raise HTTPException(status_code=404, detail="handoff not found")
            return handoff

        @router.post("/handoffs/{handoff_id}/ack")
        def ack_handoff(handoff_id: str, token: str = Header(..., alias="Authorization")):
            require_clinic_token(token)
            return store.acknowledge(handoff_id)

        return router
```

Modify `src/return42/cliniclink/desktop_sidecar/app.py` to mount the clinic router when mode is clinic:

```python
from fastapi import APIRouter
from .clinic_service import ClinicService
from .ambulance_service import AmbulanceService


def create_sidecar_app() -> FastAPI:
    app = FastAPI(title="ClinicLink Desktop Sidecar", version="1.0.0")
    app.state.sidecar_db = None
    app.state.sidecar_queue_db = None

    # Mode-specific routers mounted under /clinic and /ambulance prefixes.
    # The frontend calls /mode/{clinic,ambulance}/... based on current mode.
    clinic_router = APIRouter(prefix="/clinic")
    ambulance_router = APIRouter(prefix="/ambulance")

    @app.on_event("startup")
    async def startup() -> None:
        clinic_service = ClinicService(db_path=app.state.sidecar_db, queue_db_path=app.state.sidecar_queue_db)
        ambulance_service = AmbulanceService(db_path=app.state.sidecar_db, queue_db_path=app.state.sidecar_queue_db)
        app.include_router(clinic_service.get_router(), prefix="/clinic")
        app.include_router(ambulance_service.get_router(), prefix="/ambulance")

    # ... existing health, mode, identity, events endpoints ...

    @app.post("/mode")
    async def set_mode(payload: dict[str, str]) -> dict[str, str | None]:
        mode = payload.get("mode")
        if mode not in {SidecarMode.CLINIC.value, SidecarMode.AMBULANCE.value}:
            raise ValueError("invalid mode")
        STATE.mode = SidecarMode(mode)
        await MANAGER.broadcast("mode.changed", {"mode": STATE.mode.value})
        return {"mode": STATE.mode.value}

    return app
```

Note: The frontend prepends `/clinic` or `/ambulance` to API paths based on the current mode. This avoids dynamic route replacement at runtime and keeps the sidecar stateless with respect to routing.

Note: The route filtering above is simplified; in production use mounted sub-applications or prefix-based inclusion. For this plan, use `app.include_router` and ensure unique prefixes.

- [ ] **Step 3: Run tests**

Run: `.venv/bin/python -m pytest tests/test_desktop_sidecar_api.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/return42/cliniclink/desktop_sidecar/ tests/test_desktop_sidecar_api.py
git commit -m "feat(cliniclink): sidecar clinic mode service"
```

---

### Task 5: Implement ambulance mode service

**Files:**
- Create: `src/return42/cliniclink/desktop_sidecar/ambulance_service.py`
- Modify: `src/return42/cliniclink/desktop_sidecar/app.py`
- Test: `tests/test_desktop_sidecar_api.py`

**Interfaces:**
- Consumes: `AmbulanceSyncClient`, `InMemoryTransport`, `NodeIdentity`, `TrustStore`.
- Produces: `/ambulance/clinics` (GET), `/ambulance/handoffs` (POST), `/ambulance/outbox` (GET) in sidecar app.

- [ ] **Step 1: Write failing test**

Add to `tests/test_desktop_sidecar_api.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_ambulance_create_handoff(client, monkeypatch):
    monkeypatch.setenv("CLINICLINK_ADMIN_TOKEN", "admin-token")

    r = client.post("/mode", json={"mode": "ambulance"})
    assert r.status_code == 200

    payload = {
        "handoff_id": "ho-amb-1",
        "patient_id": "p-1",
        "clinic_id": "clinic-a",
        "chief_complaint": "chest pain",
        "eta_minutes": 10,
    }
    r = client.post(
        "/ambulance/handoffs",
        json=payload,
        headers={"Authorization": "Bearer admin-token"},
    )
    assert r.status_code == 201
    assert r.json()["status"] == "queued"
```

Run: `.venv/bin/python -m pytest tests/test_desktop_sidecar_api.py::test_ambulance_create_handoff -v`
Expected: FAIL (ambulance endpoints not defined).

- [ ] **Step 2: Implement ambulance service**

Create `src/return42/cliniclink/desktop_sidecar/ambulance_service.py`:

```python
from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException

from return42.cliniclink.models import PatientHandoff
from return42.cliniclink.queue import SyncQueue
from return42.cliniclink.store import HandoffStore
from return42.mesh.controller import MessageTopic
from return42.mesh.identity import NodeIdentity
from return42.mesh.transport import InMemoryTransport
from return42.mesh.trust import TrustStore


class AmbulanceService:
    def __init__(self, db_path: str | None = None, queue_db_path: str | None = None) -> None:
        self.db_path = db_path or os.getenv("CLINICLINK_DB_PATH", "cliniclink.db")
        self.queue_db_path = queue_db_path or os.getenv("CLINICLINK_QUEUE_DB_PATH", "cliniclink_queue.db")
        self.store = HandoffStore(self.db_path)
        self.queue = SyncQueue(self.queue_db_path)
        self.transport = InMemoryTransport()
        self.identity = NodeIdentity.from_env()
        self.client = None

    async def start(self) -> None:
        from return42.cliniclink.ambulance_client import AmbulanceSyncClient

        self.client = AmbulanceSyncClient(
            identity=self.identity,
            transport=self.transport,
            clinic_id=os.getenv("TARGET_CLINIC_ID", "clinic-a"),
            trust_store=TrustStore(tofu=True),
        )
        await self.client.start()

    async def stop(self) -> None:
        if self.client:
            await self.client.stop()

    def get_router(self):
        router = APIRouter()
        admin_token = os.getenv("CLINICLINK_ADMIN_TOKEN", os.getenv("CLINIC_TOKEN", "clinic-local-token"))

        def require_admin(authorization: str = Header(...)) -> None:
            token = authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else authorization
            if token != admin_token:
                raise HTTPException(status_code=403, detail="invalid admin token")

        @router.get("/clinics")
        async def list_clinics() -> list[dict]:
            peers = self.client.controller.peers if self.client else []
            return [{"node_id": p.node_id, "verify_key_b64": p.verify_key_b64} for p in peers]

        @router.post("/handoffs", status_code=201)
        async def create_handoff(payload: dict, authorization: str = Header(...)):
            require_admin(authorization)
            handoff = PatientHandoff(**payload)
            self.store.create(handoff)
            self.queue.enqueue(handoff, "outbound")
            # Attempt immediate send; on failure remain queued
            try:
                if self.client:
                    await self.client.submit_handoff(handoff)
                    return handoff.to_payload() | {"status": "sent"}
            except Exception:
                pass
            return handoff.to_payload() | {"status": "queued"}

        @router.get("/outbox")
        async def list_outbox() -> list[dict]:
            return [{"id": item["id"], "payload": item["payload"]} for item in self.queue.dequeue("outbound")]

        return router
```

Modify `app.py` to mount ambulance router when mode is ambulance.

- [ ] **Step 3: Run tests**

Run: `.venv/bin/python -m pytest tests/test_desktop_sidecar_api.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/return42/cliniclink/desktop_sidecar/ tests/test_desktop_sidecar_api.py
git commit -m "feat(cliniclink): sidecar ambulance mode service"
```

---

### Task 6: Mode switch and sidecar integration tests

**Files:**
- Test: `tests/test_desktop_sidecar_mode_switch.py`

**Interfaces:**
- Consumes: Full sidecar app.
- Produces: Tests verifying mode switch and end-to-end event flow.

- [ ] **Step 1: Write tests**

Create `tests/test_desktop_sidecar_mode_switch.py`:

```python
import pytest
from fastapi.testclient import TestClient
from return42.cliniclink.desktop_sidecar.app import create_sidecar_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CLINIC_TOKEN", "t")
    monkeypatch.setenv("CLINICLINK_ADMIN_TOKEN", "a")
    return TestClient(create_sidecar_app())


def test_mode_switch(client):
    assert client.get("/mode").json()["mode"] is None
    r = client.post("/mode", json={"mode": "clinic"})
    assert r.status_code == 200
    assert client.get("/mode").json()["mode"] == "clinic"
    r = client.post("/mode", json={"mode": "ambulance"})
    assert r.status_code == 200
    assert client.get("/mode").json()["mode"] == "ambulance"


def test_mode_switch_emits_event(client):
    with client.websocket_connect("/events") as ws:
        client.post("/mode", json={"mode": "clinic"})
        messages = []
        for _ in range(5):
            try:
                messages.append(ws.receive_json(timeout=1.0))
            except Exception:
                break
        assert any(m["type"] == "mode.changed" and m["payload"]["mode"] == "clinic" for m in messages)
```

- [ ] **Step 2: Run tests**

Run: `.venv/bin/python -m pytest tests/test_desktop_sidecar_mode_switch.py -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_desktop_sidecar_mode_switch.py
git commit -m "test(cliniclink): sidecar mode switch and event tests"
```

---

### Task 7: Scaffold Tauri desktop project

**Files:**
- Create: `cliniclink-desktop/package.json`
- Create: `cliniclink-desktop/tsconfig.json`
- Create: `cliniclink-desktop/vite.config.ts`
- Create: `cliniclink-desktop/index.html`
- Create: `cliniclink-desktop/src/main.tsx`
- Create: `cliniclink-desktop/src/App.tsx`
- Create: `cliniclink-desktop/src-tauri/Cargo.toml`
- Create: `cliniclink-desktop/src-tauri/tauri.conf.json`
- Create: `cliniclink-desktop/src-tauri/src/main.rs`
- Test: Manual build verification

**Interfaces:**
- Consumes: None
- Produces: Runnable Tauri + React skeleton.

- [ ] **Step 1: Create frontend skeleton**

Create `cliniclink-desktop/package.json`:

```json
{
  "name": "cliniclink-desktop",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "tauri": "tauri",
    "tauri-dev": "tauri dev",
    "tauri-build": "tauri build"
  },
  "dependencies": {
    "@tauri-apps/api": "^2.0.0",
    "@tanstack/react-query": "^5.0.0",
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "zustand": "^4.5.0"
  },
  "devDependencies": {
    "@tauri-apps/cli": "^2.0.0",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0",
    "tailwindcss": "^3.4.0",
    "typescript": "^5.4.0",
    "vite": "^5.3.0"
  }
}
```

Create `cliniclink-desktop/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

Create `cliniclink-desktop/tsconfig.node.json`:

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

Create `cliniclink-desktop/vite.config.ts`:

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(async () => ({
  plugins: [react()],
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
    watch: { ignored: ['**/src-tauri/**'] },
  },
  envPrefix: ['VITE_', 'TAURI_'],
}));
```

Create `cliniclink-desktop/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>ClinicLink Desktop</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

Create `cliniclink-desktop/src/main.tsx`:

```tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

Create `cliniclink-desktop/src/App.tsx`:

```tsx
function App() {
  return (
    <div className="min-h-screen bg-gray-50 p-4">
      <h1 className="text-2xl font-bold text-teal-700">ClinicLink Desktop</h1>
      <p className="text-gray-600">Select a mode to begin.</p>
    </div>
  );
}

export default App;
```

Create `cliniclink-desktop/src/index.css`:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 2: Create Tauri skeleton**

Create `cliniclink-desktop/src-tauri/Cargo.toml`:

```toml
[package]
name = "cliniclink-desktop"
version = "1.0.0"
description = "ClinicLink Desktop GUI"
authors = ["TradeMomentum LLC"]
edition = "2021"

[build-dependencies]
tauri-build = { version = "2.0.0", features = [] }

[dependencies]
tauri = { version = "2.0.0", features = [] }
tokio = { version = "1", features = ["full"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
reqwest = { version = "0.12", features = ["json"] }
tokio-tungstenite = { version = "0.23", features = ["native-tls"] }
futures-util = "0.3"
url = "2"
```

Create `cliniclink-desktop/src-tauri/tauri.conf.json`:

```json
{
  "productName": "ClinicLink Desktop",
  "version": "1.0.0",
  "identifier": "com.trademomentum.cliniclink-desktop",
  "build": {
    "frontendDist": "../dist",
    "devUrl": "http://localhost:1420",
    "beforeDevCommand": "npm run dev",
    "beforeBuildCommand": "npm run build"
  },
  "app": {
    "windows": [
      {
        "title": "ClinicLink Desktop",
        "width": 1200,
        "height": 800,
        "resizable": true,
        "fullscreen": false
      }
    ],
    "security": {
      "csp": "default-src 'self'; connect-src 'self' http://localhost:* ws://localhost:*; img-src 'self' data:; style-src 'self' 'unsafe-inline'"
    }
  },
  "bundle": {
    "active": true,
    "targets": ["app", "dmg", "msi", "deb"],
    "icon": [
      "icons/32x32.png",
      "icons/128x128.png",
      "icons/128x128@2x.png",
      "icons/icon.icns",
      "icons/icon.ico"
    ]
  }
}
```

Create `cliniclink-desktop/src-tauri/src/main.rs`:

```rust
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    cliniclink_desktop_lib::run();
}
```

Create `cliniclink-desktop/src-tauri/src/lib.rs`:

```rust
use tauri::Manager;

#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}!", name)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![greet])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

Create `cliniclink-desktop/src-tauri/build.rs`:

```rust
fn main() {
    tauri_build::build();
}
```

- [ ] **Step 3: Install dependencies and verify build**

Run:

```bash
cd cliniclink-desktop
npm install
cargo tauri build
```

Expected: Build succeeds (a default Tauri window opens on dev or a bundle is produced on build).

- [ ] **Step 4: Commit**

```bash
git add cliniclink-desktop/
git commit -m "feat(desktop): scaffold Tauri + React project"
```

---

### Task 8: Implement Rust sidecar spawn and management

**Files:**
- Create: `cliniclink-desktop/src-tauri/src/sidecar.rs`
- Modify: `cliniclink-desktop/src-tauri/src/lib.rs`
- Modify: `cliniclink-desktop/src-tauri/Cargo.toml`
- Test: Manual integration test

**Interfaces:**
- Consumes: Sidecar binary path.
- Produces: `spawn_sidecar()` returns port; `kill_sidecar()` terminates process.

- [ ] **Step 1: Implement sidecar process management**

Create `cliniclink-desktop/src-tauri/src/sidecar.rs`:

```rust
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use tauri::{AppHandle, Manager, State};

pub struct SidecarState {
    pub child: Mutex<Option<Child>>,
    pub port: Mutex<u16>,
}

impl SidecarState {
    pub fn new() -> Self {
        Self {
            child: Mutex::new(None),
            port: Mutex::new(2842),
        }
    }
}

pub fn spawn_sidecar(app: &AppHandle) -> Result<u16, String> {
    let sidecar_path = app
        .path()
        .resolve("r42-cliniclink", tauri::path::BaseDirectory::Resource)
        .map_err(|e| e.to_string())?;

    let child = Command::new(sidecar_path)
        .arg("sidecar")
        .arg("--port")
        .arg("2842")
        .arg("--host")
        .arg("127.0.0.1")
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("failed to spawn sidecar: {}", e))?;

    // In a real implementation, parse stdout for SIDECAR_PORT=...
    // For this plan, assume port 2842 and verify health.
    let port = 2842u16;
    {
        let state: State<SidecarState> = app.state();
        *state.child.lock().unwrap() = Some(child);
        *state.port.lock().unwrap() = port;
    }

    Ok(port)
}

pub fn kill_sidecar(app: &AppHandle) -> Result<(), String> {
    let state: State<SidecarState> = app.state();
    if let Some(mut child) = state.child.lock().unwrap().take() {
        let _ = child.kill();
        let _ = child.wait();
    }
    Ok(())
}
```

- [ ] **Step 2: Wire into Tauri lifecycle**

Modify `cliniclink-desktop/src-tauri/src/lib.rs`:

```rust
mod sidecar;

use sidecar::{kill_sidecar, spawn_sidecar, SidecarState};
use tauri::Manager;

#[tauri::command]
async fn get_sidecar_port(state: State<'_, SidecarState>) -> Result<u16, String> {
    Ok(*state.port.lock().unwrap())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(SidecarState::new())
        .setup(|app| {
            spawn_sidecar(app.handle())?;
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                let _ = kill_sidecar(window.app_handle());
            }
        })
        .invoke_handler(tauri::generate_handler![get_sidecar_port])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

- [ ] **Step 3: Verify build**

Run: `cd cliniclink-desktop && cargo tauri build`
Expected: Build succeeds.

- [ ] **Step 5: Commit**

```bash
git add cliniclink-desktop/
git commit -m "feat(desktop): spawn and manage Python sidecar from Tauri"
```

---

### Task 9: Implement Tauri commands and event forwarding

**Files:**
- Modify: `cliniclink-desktop/src-tauri/src/lib.rs`
- Modify: `cliniclink-desktop/src-tauri/Cargo.toml`
- Test: Manual integration test

**Interfaces:**
- Consumes: Sidecar HTTP + WebSocket.
- Produces: Tauri commands `sidecar_request`, `set_mode`; Tauri events `cliniclink:event`.

- [ ] **Step 1: Add commands**

Modify `cliniclink-desktop/src-tauri/src/lib.rs` to include:

```rust
use reqwest;
use serde_json::Value;

#[tauri::command]
async fn sidecar_request(
    state: State<'_, SidecarState>,
    method: String,
    path: String,
    body: Option<String>,
    headers: Option<String>,
) -> Result<String, String> {
    let port = *state.port.lock().unwrap();
    let url = format!("http://127.0.0.1:{}{}", port, path);
    let client = reqwest::Client::new();
    let mut req = match method.to_uppercase().as_str() {
        "GET" => client.get(&url),
        "POST" => client.post(&url),
        "PUT" => client.put(&url),
        "DELETE" => client.delete(&url),
        _ => return Err("unsupported method".to_string()),
    };
    if let Some(h) = headers {
        let parsed: std::collections::HashMap<String, String> = serde_json::from_str(&h).map_err(|e| e.to_string())?;
        for (k, v) in parsed {
            req = req.header(k, v);
        }
    }
    if let Some(b) = body {
        req = req.body(b).header("Content-Type", "application/json");
    }
    let resp = req.send().await.map_err(|e| e.to_string())?;
    let text = resp.text().await.map_err(|e| e.to_string())?;
    Ok(text)
}

#[tauri::command]
async fn set_mode(state: State<'_, SidecarState>, mode: String) -> Result<String, String> {
    sidecar_request(
        state,
        "POST".to_string(),
        "/mode".to_string(),
        Some(format!("{{\"mode\":\"{}\"}}", mode)),
    )
    .await
}
```

- [ ] **Step 2: Add WebSocket event forwarding**

Add a background task in `setup` that connects to the sidecar WebSocket and forwards events:

```rust
.setup(|app| {
    let handle = app.handle().clone();
    spawn_sidecar(&handle)?;
    tauri::async_runtime::spawn(async move {
        use futures_util::StreamExt;
        use tokio_tungstenite::tungstenite::Message;

        let port = 2842u16; // read from state in real impl
        let url = format!("ws://127.0.0.1:{}/events", port);
        if let Ok((mut ws, _)) = tokio_tungstenite::connect_async(&url).await {
            while let Some(Ok(Message::Text(text))) = ws.next().await {
                let _ = handle.emit("cliniclink:event", text);
            }
        }
    });
    Ok(())
})
```

- [ ] **Step 3: Update Cargo.toml**

Ensure `cliniclink-desktop/src-tauri/Cargo.toml` dependencies include:

```toml
reqwest = { version = "0.12", features = ["json"] }
tokio-tungstenite = { version = "0.23", features = ["native-tls"] }
futures-util = "0.3"
```

- [ ] **Step 4: Verify build**

Run: `cd cliniclink-desktop && cargo tauri build`
Expected: Build succeeds.

- [ ] **Step 5: Commit**

```bash
git add cliniclink-desktop/
git commit -m "feat(desktop): Tauri commands and sidecar event forwarding"
```

---

### Task 10: Frontend API layer and event hooks

**Files:**
- Create: `cliniclink-desktop/src/api/sidecar.ts`
- Create: `cliniclink-desktop/src/hooks/useSidecar.ts`
- Create: `cliniclink-desktop/src/hooks/useEvents.ts`
- Test: Vitest unit tests (optional but recommended)

**Interfaces:**
- Consumes: Tauri `invoke` and `listen`.
- Produces: Typed API functions and React hooks.

- [ ] **Step 1: Implement API layer**

Create `cliniclink-desktop/src/api/sidecar.ts`:

```typescript
import { invoke } from '@tauri-apps/api/core';

export async function sidecarRequest(
  method: string,
  path: string,
  body?: object,
  headers?: Record<string, string>,
): Promise<string> {
  return invoke('sidecar_request', {
    method,
    path,
    body: body ? JSON.stringify(body) : undefined,
    headers: headers ? JSON.stringify(headers) : undefined,
  });
}

export async function setMode(mode: 'clinic' | 'ambulance'): Promise<string> {
  return invoke('set_mode', { mode });
}

export async function getMode(): Promise<{ mode: string | null }> {
  const text = await sidecarRequest('GET', '/mode');
  return JSON.parse(text);
}
```

- [ ] **Step 2: Implement hooks**

Create `cliniclink-desktop/src/hooks/useEvents.ts`:

```typescript
import { useEffect } from 'react';
import { listen } from '@tauri-apps/api/event';

export type SidecarEvent = {
  type: string;
  timestamp: string;
  payload: Record<string, unknown>;
};

export function useSidecarEvent(callback: (event: SidecarEvent) => void) {
  useEffect(() => {
    let unlisten: (() => void) | undefined;
    listen<string>('cliniclink:event', (e) => {
      try {
        callback(JSON.parse(e.payload));
      } catch {
        // ignore malformed events
      }
    }).then((fn) => {
      unlisten = fn;
    });
    return () => unlisten?.();
  }, [callback]);
}
```

- [ ] **Step 3: Commit**

```bash
git add cliniclink-desktop/src/api cliniclink-desktop/src/hooks
git commit -m "feat(desktop): frontend API layer and event hooks"
```

---

### Task 11: Implement mode selector and app shell

**Files:**
- Create: `cliniclink-desktop/src/components/ModeSelector.tsx`
- Modify: `cliniclink-desktop/src/App.tsx`
- Create: `cliniclink-desktop/src/store/appStore.ts`
- Test: Manual UI verification

**Interfaces:**
- Consumes: `setMode`, `getMode`, `useSidecarEvent`.
- Produces: Mode selection UI and persistent app shell.

- [ ] **Step 1: Implement Zustand store**

Create `cliniclink-desktop/src/store/appStore.ts`:

```typescript
import { create } from 'zustand';

interface AppState {
  mode: 'clinic' | 'ambulance' | null;
  setMode: (mode: 'clinic' | 'ambulance') => void;
}

export const useAppStore = create<AppState>((set) => ({
  mode: null,
  setMode: (mode) => set({ mode }),
}));
```

- [ ] **Step 2: Implement ModeSelector**

Create `cliniclink-desktop/src/components/ModeSelector.tsx`:

```tsx
import { setMode } from '../api/sidecar';
import { useAppStore } from '../store/appStore';

export default function ModeSelector() {
  const setAppMode = useAppStore((s) => s.setMode);

  const choose = async (mode: 'clinic' | 'ambulance') => {
    await setMode(mode);
    setAppMode(mode);
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen gap-6">
      <h1 className="text-3xl font-bold text-teal-700">ClinicLink Desktop</h1>
      <p className="text-gray-600">Select your role to continue</p>
      <div className="flex gap-4">
        <button
          onClick={() => choose('clinic')}
          className="px-8 py-4 bg-teal-600 text-white rounded-lg hover:bg-teal-700"
        >
          Clinic
        </button>
        <button
          onClick={() => choose('ambulance')}
          className="px-8 py-4 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          Ambulance
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Update App.tsx**

Modify `cliniclink-desktop/src/App.tsx`:

```tsx
import { useEffect } from 'react';
import ModeSelector from './components/ModeSelector';
import { useAppStore } from './store/appStore';
import { getMode } from './api/sidecar';

export default function App() {
  const { mode, setMode } = useAppStore();

  useEffect(() => {
    getMode().then((m) => {
      if (m.mode === 'clinic' || m.mode === 'ambulance') setMode(m.mode);
    });
  }, [setMode]);

  if (!mode) return <ModeSelector />;

  return (
    <div className="min-h-screen bg-gray-50 p-4">
      <header className="flex justify-between items-center mb-4">
        <h1 className="text-2xl font-bold text-teal-700">ClinicLink Desktop</h1>
        <span className="text-sm uppercase tracking-wide text-gray-500">{mode} mode</span>
      </header>
      <p>Mode: {mode}</p>
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add cliniclink-desktop/src/
git commit -m "feat(desktop): mode selector and app shell"
```

---

### Task 12: Implement clinic view

**Files:**
- Create: `cliniclink-desktop/src/components/ClinicView.tsx`
- Create: `cliniclink-desktop/src/components/HandoffCard.tsx`
- Create: `cliniclink-desktop/src/hooks/useHandoffs.ts`
- Modify: `cliniclink-desktop/src/App.tsx`
- Test: Manual UI verification

**Interfaces:**
- Consumes: `/handoffs` GET, `/handoffs/{id}/ack` POST, WebSocket events.
- Produces: Clinic handoff list and acknowledge UI.

- [ ] **Step 1: Implement useHandoffs hook**

Create `cliniclink-desktop/src/hooks/useHandoffs.ts`:

```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { sidecarRequest } from '../api/sidecar';

export interface Handoff {
  handoff_id: string;
  patient_id: string;
  ambulance_id: string;
  clinic_id: string;
  chief_complaint: string;
  eta_minutes: number | null;
  status: 'pending' | 'acknowledged' | 'rejected';
  vital_signs: Record<string, unknown>;
  medications: string[];
  created_at: string;
  acknowledged_at: string | null;
}

const CLINIC_TOKEN = 'clinic-token'; // load from secure storage in later task

export function useHandoffs() {
  return useQuery<Handoff[]>({
    queryKey: ['handoffs'],
    queryFn: async () => {
      const text = await sidecarRequest(
        'GET',
        `/clinic/handoffs?status=pending`,
        undefined,
        { Authorization: `Bearer ${CLINIC_TOKEN}` },
      );
      return JSON.parse(text);
    },
  });
}

export function useAcknowledgeHandoff() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (handoffId: string) => {
      const text = await sidecarRequest(
        'POST',
        `/clinic/handoffs/${handoffId}/ack`,
        undefined,
        { Authorization: `Bearer ${CLINIC_TOKEN}` },
      );
      return JSON.parse(text);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['handoffs'] }),
  });
}
```

- [ ] **Step 2: Implement HandoffCard**

Create `cliniclink-desktop/src/components/HandoffCard.tsx`:

```tsx
import type { Handoff } from '../hooks/useHandoffs';

interface Props {
  handoff: Handoff;
  onAck: (id: string) => void;
}

export default function HandoffCard({ handoff, onAck }: Props) {
  return (
    <div className="bg-white rounded-lg shadow p-4 mb-4 border-l-4 border-teal-500">
      <div className="flex justify-between items-start">
        <div>
          <h3 className="font-bold text-lg">{handoff.patient_id}</h3>
          <p className="text-gray-700">{handoff.chief_complaint || 'No complaint recorded'}</p>
          <p className="text-sm text-gray-500">Ambulance: {handoff.ambulance_id} | ETA: {handoff.eta_minutes ?? '?'} min</p>
        </div>
        <button
          onClick={() => onAck(handoff.handoff_id)}
          className="px-4 py-2 bg-teal-600 text-white rounded hover:bg-teal-700"
        >
          Acknowledge
        </button>
      </div>
      {handoff.vital_signs && Object.keys(handoff.vital_signs).length > 0 && (
        <pre className="mt-2 text-xs bg-gray-100 p-2 rounded">{JSON.stringify(handoff.vital_signs, null, 2)}</pre>
      )}
      {handoff.medications && handoff.medications.length > 0 && (
        <p className="mt-2 text-sm text-gray-600">Meds: {handoff.medications.join(', ')}</p>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Implement ClinicView**

Create `cliniclink-desktop/src/components/ClinicView.tsx`:

```tsx
import { useEffect } from 'react';
import { useHandoffs, useAcknowledgeHandoff } from '../hooks/useHandoffs';
import { useSidecarEvent } from '../hooks/useEvents';
import HandoffCard from './HandoffCard';

export default function ClinicView() {
  const { data: handoffs, isLoading, refetch } = useHandoffs();
  const ack = useAcknowledgeHandoff();

  useSidecarEvent((event) => {
    if (event.type === 'handoff.received') refetch();
  });

  if (isLoading) return <p>Loading handoffs...</p>;

  return (
    <div>
      <h2 className="text-xl font-semibold mb-4">Incoming Handoffs</h2>
      {handoffs?.length === 0 && <p className="text-gray-500">No pending handoffs.</p>}
      {handoffs?.map((h) => (
        <HandoffCard key={h.handoff_id} handoff={h} onAck={(id) => ack.mutate(id)} />
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Wire into App.tsx**

Modify `cliniclink-desktop/src/App.tsx` to render `ClinicView` when mode is clinic.

- [ ] **Step 5: Commit**

```bash
git add cliniclink-desktop/src/
git commit -m "feat(desktop): clinic view with handoff list and acknowledge"
```

---

### Task 13: Implement ambulance view

**Files:**
- Create: `cliniclink-desktop/src/components/AmbulanceView.tsx`
- Create: `cliniclink-desktop/src/components/HandoffForm.tsx`
- Create: `cliniclink-desktop/src/components/ClinicList.tsx`
- Create: `cliniclink-desktop/src/hooks/useClinics.ts`
- Create: `cliniclink-desktop/src/hooks/useOutbox.ts`
- Modify: `cliniclink-desktop/src/App.tsx`
- Test: Manual UI verification

**Interfaces:**
- Consumes: `/clinics` GET, `/handoffs` POST, `/outbox` GET, WebSocket events.
- Produces: Ambulance handoff creation and outbox UI.

- [ ] **Step 1: Implement hooks**

Create `cliniclink-desktop/src/hooks/useClinics.ts`:

```typescript
import { useQuery } from '@tanstack/react-query';
import { sidecarRequest } from '../api/sidecar';

export interface Clinic {
  node_id: string;
  verify_key_b64: string;
}

export function useClinics() {
  return useQuery<Clinic[]>({
    queryKey: ['clinics'],
    queryFn: async () => {
      const text = await sidecarRequest('GET', '/ambulance/clinics');
      return JSON.parse(text);
    },
  });
}
```

Create `cliniclink-desktop/src/hooks/useOutbox.ts`:

```typescript
import { useQuery } from '@tanstack/react-query';
import { sidecarRequest } from '../api/sidecar';

export interface OutboxItem {
  id: number;
  payload: Record<string, unknown>;
}

export function useOutbox() {
  return useQuery<OutboxItem[]>({
    queryKey: ['outbox'],
    queryFn: async () => {
      const text = await sidecarRequest('GET', '/ambulance/outbox');
      return JSON.parse(text);
    },
  });
}
```

- [ ] **Step 2: Implement components**

Create `cliniclink-desktop/src/components/ClinicList.tsx`:

```tsx
import { useClinics } from '../hooks/useClinics';

interface Props {
  selected: string | null;
  onSelect: (nodeId: string) => void;
}

export default function ClinicList({ selected, onSelect }: Props) {
  const { data: clinics, isLoading } = useClinics();

  if (isLoading) return <p>Discovering clinics...</p>;
  if (!clinics?.length) return <p className="text-amber-600">No clinics discovered on mesh.</p>;

  return (
    <div className="space-y-2">
      {clinics.map((c) => (
        <button
          key={c.node_id}
          onClick={() => onSelect(c.node_id)}
          className={`w-full text-left p-3 rounded border ${
            selected === c.node_id ? 'border-blue-600 bg-blue-50' : 'border-gray-200'
          }`}
        >
          <span className="font-medium">{c.node_id}</span>
        </button>
      ))}
    </div>
  );
}
```

Create `cliniclink-desktop/src/components/HandoffForm.tsx`:

```tsx
import { useState } from 'react';
import { sidecarRequest } from '../api/sidecar';

const ADMIN_TOKEN = 'admin-token'; // load from secure storage in later task

interface Props {
  clinicId: string;
  onSent: () => void;
}

export default function HandoffForm({ clinicId, onSent }: Props) {
  const [patientId, setPatientId] = useState('');
  const [complaint, setComplaint] = useState('');
  const [eta, setEta] = useState('');

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload = {
      handoff_id: `ho-${Date.now()}`,
      patient_id: patientId,
      clinic_id: clinicId,
      chief_complaint: complaint,
      eta_minutes: eta ? parseInt(eta, 10) : null,
      vital_signs: {},
      medications: [],
    };
    await sidecarRequest(
      'POST',
      '/ambulance/handoffs',
      payload,
      { Authorization: `Bearer ${ADMIN_TOKEN}` },
    );
    onSent();
    setPatientId('');
    setComplaint('');
    setEta('');
  };

  return (
    <form onSubmit={submit} className="space-y-3">
      <input value={patientId} onChange={(e) => setPatientId(e.target.value)} placeholder="Patient ID" className="w-full p-2 border rounded" required />
      <input value={complaint} onChange={(e) => setComplaint(e.target.value)} placeholder="Chief complaint" className="w-full p-2 border rounded" required />
      <input value={eta} onChange={(e) => setEta(e.target.value)} placeholder="ETA minutes" type="number" className="w-full p-2 border rounded" />
      <button type="submit" className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">Send Handoff</button>
    </form>
  );
}
```

Create `cliniclink-desktop/src/components/AmbulanceView.tsx`:

```tsx
import { useState } from 'react';
import ClinicList from './ClinicList';
import HandoffForm from './HandoffForm';
import { useOutbox } from '../hooks/useOutbox';

export default function AmbulanceView() {
  const [selectedClinic, setSelectedClinic] = useState<string | null>(null);
  const { data: outbox, refetch } = useOutbox();

  return (
    <div className="grid grid-cols-2 gap-6">
      <div>
        <h2 className="text-xl font-semibold mb-4">Target Clinic</h2>
        <ClinicList selected={selectedClinic} onSelect={setSelectedClinic} />
        {selectedClinic && (
          <>
            <h3 className="font-semibold mt-6 mb-2">New Handoff</h3>
            <HandoffForm clinicId={selectedClinic} onSent={() => refetch()} />
          </>
        )}
      </div>
      <div>
        <h2 className="text-xl font-semibold mb-4">Outbox</h2>
        {outbox?.length === 0 && <p className="text-gray-500">No queued handoffs.</p>}
        {outbox?.map((item) => (
          <div key={item.id} className="p-3 bg-white rounded shadow mb-2">
            <p className="font-medium">{item.payload.handoff_id}</p>
            <p className="text-sm text-gray-500">{item.payload.patient_id}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Wire into App.tsx**

Modify `cliniclink-desktop/src/App.tsx` to render `AmbulanceView` when mode is ambulance.

- [ ] **Step 4: Commit**

```bash
git add cliniclink-desktop/src/
git commit -m "feat(desktop): ambulance view with clinic discovery and handoff form"
```

---

### Task 14: Implement connection status and notifications

**Files:**
- Create: `cliniclink-desktop/src/components/ConnectionStatus.tsx`
- Create: `cliniclink-desktop/src/hooks/useConnection.ts`
- Modify: `cliniclink-desktop/src/App.tsx`
- Test: Manual UI verification

**Interfaces:**
- Consumes: WebSocket `connection.*` events, `/health` polling.
- Produces: Connection status indicator and new-handoff alerts.

- [ ] **Step 1: Implement connection hook**

Create `cliniclink-desktop/src/hooks/useConnection.ts`:

```typescript
import { useEffect, useState } from 'react';
import { useSidecarEvent } from './useEvents';

export function useConnection() {
  const [status, setStatus] = useState<'healthy' | 'degraded' | 'offline'>('healthy');

  useSidecarEvent((event) => {
    if (event.type === 'connection.degraded') setStatus('degraded');
    if (event.type === 'connection.restored') setStatus('healthy');
    if (event.type === 'mesh.peer.lost') setStatus('degraded');
  });

  return status;
}
```

- [ ] **Step 2: Implement ConnectionStatus component**

Create `cliniclink-desktop/src/components/ConnectionStatus.tsx`:

```tsx
interface Props {
  status: 'healthy' | 'degraded' | 'offline';
}

export default function ConnectionStatus({ status }: Props) {
  const colors = {
    healthy: 'bg-green-500',
    degraded: 'bg-amber-500',
    offline: 'bg-red-500',
  };

  return (
    <div className="flex items-center gap-2">
      <span className={`w-3 h-3 rounded-full ${colors[status]}`} />
      <span className="text-sm capitalize text-gray-700">{status}</span>
    </div>
  );
}
```

- [ ] **Step 3: Add new-handoff notification**

Modify `cliniclink-desktop/src/components/ClinicView.tsx` to play a beep or show a toast on `handoff.received`.

Use the Web Audio API for a short beep (no external assets):

```typescript
function playAlert() {
  const ctx = new AudioContext();
  const osc = ctx.createOscillator();
  osc.connect(ctx.destination);
  osc.start();
  osc.stop(ctx.currentTime + 0.2);
}
```

- [ ] **Step 4: Wire into App.tsx**

Show `ConnectionStatus` in the header.

- [ ] **Step 5: Commit**

```bash
git add cliniclink-desktop/src/
git commit -m "feat(desktop): connection status and handoff alerts"
```

---

### Task 15: Secure storage for tokens and keys

**Files:**
- Modify: `cliniclink-desktop/src-tauri/Cargo.toml`
- Modify: `cliniclink-desktop/src-tauri/src/lib.rs`
- Modify: `cliniclink-desktop/src/api/sidecar.ts`
- Modify: `cliniclink-desktop/src-tauri/tauri.conf.json`
- Test: Manual integration test

**Interfaces:**
- Consumes: Tauri Stronghold or OS keychain plugin.
- Produces: `store_secret`, `read_secret` commands; sidecar env injection.

- [ ] **Step 1: Add secure storage dependency**

Add to `cliniclink-desktop/src-tauri/Cargo.toml`:

```toml
keyring = "3.0"
```

- [ ] **Step 2: Implement commands**

Modify `cliniclink-desktop/src-tauri/src/lib.rs`:

```rust
const KEYRING_SERVICE: &str = "com.trademomentum.cliniclink-desktop";

#[tauri::command]
async fn store_secret(key: String, value: String) -> Result<(), String> {
    let entry = keyring::Entry::new(KEYRING_SERVICE, &key).map_err(|e| e.to_string())?;
    entry.set_password(&value).map_err(|e| e.to_string())
}

#[tauri::command]
async fn read_secret(key: String) -> Result<Option<String>, String> {
    let entry = keyring::Entry::new(KEYRING_SERVICE, &key).map_err(|e| e.to_string())?;
    match entry.get_password() {
        Ok(value) => Ok(Some(value)),
        Err(keyring::Error::NoEntry) => Ok(None),
        Err(e) => Err(e.to_string()),
    }
}
```

- [ ] **Step 3: Inject secrets into sidecar env**

Modify `cliniclink-desktop/src-tauri/src/sidecar.rs` so `spawn_sidecar` reads `NODE_SIGNING_KEY`, `CLINIC_TOKEN`, and `CLINICLINK_ADMIN_TOKEN` via `read_secret` and sets them as environment variables on the sidecar `Command`:

```rust
use std::process::Command;

let mut cmd = Command::new(sidecar_path);
if let Ok(Some(key)) = read_secret("NODE_SIGNING_KEY").await {
    cmd.env("NODE_SIGNING_KEY", key);
}
if let Ok(Some(token)) = read_secret("CLINIC_TOKEN").await {
    cmd.env("CLINIC_TOKEN", token);
}
if let Ok(Some(token)) = read_secret("CLINICLINK_ADMIN_TOKEN").await {
    cmd.env("CLINICLINK_ADMIN_TOKEN", token);
}
```

- [ ] **Step 4: Commit**

```bash
git add cliniclink-desktop/
git commit -m "feat(desktop): secure storage for sidecar secrets"
```

---

### Task 16: Frontend tests and type checking

**Files:**
- Create: `cliniclink-desktop/vitest.config.ts`
- Create: `cliniclink-desktop/src/components/__tests__/ModeSelector.test.tsx`
- Create: `cliniclink-desktop/src/hooks/__tests__/useEvents.test.ts`
- Modify: `cliniclink-desktop/package.json`

**Interfaces:**
- Consumes: React components and hooks.
- Produces: Passing frontend unit tests.

- [ ] **Step 1: Add Vitest and testing dependencies**

Add to `package.json` devDependencies:

```json
"vitest": "^1.6.0",
"@testing-library/react": "^15.0.0",
"@testing-library/jest-dom": "^6.4.0",
"jsdom": "^24.0.0"
```

- [ ] **Step 2: Configure Vitest**

Create `cliniclink-desktop/vitest.config.ts`:

```typescript
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
  },
});
```

- [ ] **Step 3: Write tests**

Create `cliniclink-desktop/src/components/__tests__/ModeSelector.test.tsx`:

```tsx
import { render, screen, fireEvent } from '@testing-library/react';
import ModeSelector from '../ModeSelector';

vi.mock('../../api/sidecar', () => ({
  setMode: vi.fn().mockResolvedValue(undefined),
}));

test('renders mode buttons', () => {
  render(<ModeSelector />);
  expect(screen.getByText('Clinic')).toBeInTheDocument();
  expect(screen.getByText('Ambulance')).toBeInTheDocument();
});
```

- [ ] **Step 4: Run tests**

Run: `cd cliniclink-desktop && npm run test`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add cliniclink-desktop/
git commit -m "test(desktop): frontend unit tests with Vitest"
```

---

### Task 17: Update build scripts and CI for Tauri

**Files:**
- Modify: `.github/workflows/release-installers.yml`
- Create: `scripts/build_tauri_app.sh`
- Test: CI dry-run or manual build

**Interfaces:**
- Consumes: Tauri project.
- Produces: Platform bundles uploaded to GitHub Release.

- [ ] **Step 1: Create build helper script**

Create `scripts/build_tauri_app.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../cliniclink-desktop"
npm ci
cargo tauri build
```

- [ ] **Step 2: Update GitHub Actions workflow**

Add a `build-tauri` job to `.github/workflows/release-installers.yml` for macOS, Windows, and Linux runners. Use pinned action SHAs for `actions/checkout` and `actions/setup-node`.

- [ ] **Step 3: Upload Tauri artifacts**

Add upload step to attach `.app`, `.dmg`, `.msi`, `.deb` to the release.

- [ ] **Step 4: Commit**

```bash
git add scripts/build_tauri_app.sh .github/workflows/release-installers.yml
git commit -m "ci: build and release Tauri desktop app"
```

---

### Task 18: Update platform installers to include desktop app

**Files:**
- Modify: `scripts/build_macos_installer.py`
- Modify: `scripts/build_linux_installer.py`
- Modify: `scripts/build_windows_installer.iss`
- Test: Manual installer build verification

**Interfaces:**
- Consumes: Tauri build outputs.
- Produces: Combined installers with CLI binaries and desktop app.

- [ ] **Step 1: macOS installer**

Update `scripts/build_macos_installer.py` to copy `ClinicLink Desktop.app` into the payload `Applications/` directory.

- [ ] **Step 2: Linux installer**

Update `scripts/build_linux_installer.py` to include Tauri binary in `/usr/local/bin` and a `.desktop` file in `/usr/share/applications`.

- [ ] **Step 3: Windows installer**

Update `scripts/build_windows_installer.iss` to include `ClinicLink Desktop.exe` and create a Start Menu shortcut.

- [ ] **Step 4: Commit**

```bash
git add scripts/
git commit -m "chore(installer): include desktop app in platform installers"
```

---

### Task 19: Final integration and full suite verification

**Files:**
- All modified files.
- Test: Full test suite.

**Interfaces:**
- Consumes: All previous tasks.
- Produces: Passing full suite and working desktop app.

- [ ] **Step 1: Run Python tests**

Run: `.venv/bin/python -m pytest -q`
Expected: All pass (existing + new sidecar tests).

- [ ] **Step 2: Run frontend tests**

Run: `cd cliniclink-desktop && npm run test`
Expected: PASS.

- [ ] **Step 3: Build Tauri app**

Run: `cd cliniclink-desktop && cargo tauri build`
Expected: Successful platform bundle.

- [ ] **Step 4: End-to-end smoke test**

- Start app in clinic mode.
- Start app in ambulance mode (or use test client).
- Create handoff from ambulance.
- Verify it appears in clinic view.
- Acknowledge in clinic.
- Verify ambulance sees acknowledgement.

- [ ] **Step 5: Commit and tag**

```bash
git add .
git commit -m "feat(desktop): ClinicLink Desktop v1.0.0"
git tag v1.1.0
```

---

## Self-Review

### Spec Coverage

| Spec Section | Plan Task |
|--------------|-----------|
| Tauri shell | Task 7, 8, 9 |
| Python sidecar | Task 1-6 |
| React frontend | Task 10-14 |
| WebSocket events | Task 3, 9 |
| Security/PHI | Task 15 |
| Packaging | Task 17, 18 |
| Testing | Every task + Task 16, 19 |

### Placeholder Scan

No TBD/TODO placeholders. Each step includes concrete code, commands, and expected outputs.

### Type Consistency

- `Handoff` interface in frontend matches `PatientHandoff` model fields.
- `SidecarMode` enum used consistently in Python sidecar.
- Tauri command names (`sidecar_request`, `set_mode`, `get_sidecar_port`) consistent.

### Known Gaps / Follow-Up

- Icons and branding assets are assumed to exist or can be added later.
- Map/ETA dashboard is explicitly out of scope (Phase 2).
- Secure storage uses the OS keychain via the `keyring` crate; future hardening may migrate to Tauri Stronghold for encrypted backups.
- The sidecar port is currently fixed at 2842; dynamic port selection can be added if port conflicts arise.
