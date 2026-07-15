# Phase 1: Local Mesh Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a software-simulated local mesh baseline where SOM nodes discover peers, exchange heartbeats, and send/receive authenticated messages using an in-memory transport for tests and an MQTT transport for sandbox/integration.

**Architecture:** A `MeshNode` has an identity (node_id, key) and participates via a `MeshTransport` abstraction. `InMemoryTransport` enables fast unit tests; `MqttTransport` (via `aiomqtt`) targets real sandbox runs. `SmeshController` orchestrates discovery, periodic heartbeats, and message routing. Messages are typed Pydantic models with source, destination, topic, payload, and timestamp. The controller emits telemetry events through the existing observability bus and writes evidence logs.

**Tech Stack:** Python 3.11+, aiomqtt, pydantic, pytest-asyncio, return42.observability.

## Global Constraints

- Python version floor: **3.11**
- All runtime configuration via environment variables with sensible defaults.
- Evidence logs are **append-only JSONL**; never overwrite existing log files.
- Prometheus metrics use `prometheus_client` default registry.
- All tests use **pytest** and run with `pytest -q`.
- File paths are relative to repository root; source code lives under `src/return42/`.
- Commit messages follow conventional commits (`feat:`, `test:`, `docs:`, `chore:`).
- No production secrets in code; use `.env` files or environment variables.
- Mesh messages must include identity metadata and a signature placeholder for future HMAC work.

---

## File Structure

```
.
├── src/return42/
│   └── mesh/
│       ├── __init__.py
│       ├── identity.py
│       ├── message.py
│       ├── transport.py
│       ├── transport_mqtt.py
│       ├── controller.py
│       └── cli.py
├── tests/
│   ├── test_mesh_identity.py
│   ├── test_mesh_message.py
│   ├── test_mesh_transport.py
│   ├── test_mesh_controller.py
│   └── test_mesh_sandbox.py
└── scripts/
    └── run_mesh_sandbox.py
```

---

### Task 1: Add Mesh Dependencies

**Files:**
- Modify: `pyproject.toml`
- Test: `tests/test_mesh_imports.py`

**Interfaces:**
- Consumes: Existing `pyproject.toml`.
- Produces: `aiomqtt>=2.0.0` dependency; `tests/test_mesh_imports.py` verifies `return42.mesh` imports.

- [ ] **Step 1: Write the failing test**

Create `tests/test_mesh_imports.py`:

```python
def test_mesh_package_imports():
    import return42.mesh
    import return42.mesh.identity
    import return42.mesh.message
    import return42.mesh.transport
    import return42.mesh.controller
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_mesh_imports.py::test_mesh_package_imports -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'return42.mesh'`

- [ ] **Step 3: Add dependency and package marker**

Modify `pyproject.toml` dependencies:

```toml
dependencies = [
    "fastapi>=0.111.0",
    "uvicorn[standard]>=0.30.0",
    "prometheus-client>=0.20.0",
    "pydantic>=2.7.0",
    "typer>=0.12.0",
    "aiomqtt>=2.0.0",
]
```

Create `src/return42/mesh/__init__.py`:

```python
"""Return42 local mesh plane."""
```

- [ ] **Step 4: Install and run test**

Run:

```bash
python -m pip install -e .
pytest tests/test_mesh_imports.py::test_mesh_package_imports -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/return42/mesh/__init__.py tests/test_mesh_imports.py
git commit -m "chore: add aiomqtt dependency and mesh package scaffold"
```

---

### Task 2: Mesh Node Identity and Message Schema

**Files:**
- Create: `src/return42/mesh/identity.py`
- Create: `src/return42/mesh/message.py`
- Create: `tests/test_mesh_identity.py`
- Create: `tests/test_mesh_message.py`

**Interfaces:**
- Consumes: pydantic.
- Produces:
  - `NodeIdentity`: `node_id`, `public_key` (str), `private_key` (str, optional).
  - `MeshMessage`: `msg_id`, `source`, `destination`, `topic`, `payload`, `timestamp`, `signature` (optional).
  - `MessageTopic`: enum or constants for `heartbeat`, `discovery`, `command`.

- [ ] **Step 1: Write failing tests**

Create `tests/test_mesh_identity.py`:

```python
from return42.mesh.identity import NodeIdentity


def test_node_identity_creation():
    node = NodeIdentity(node_id="som-01")
    assert node.node_id == "som-01"
    assert node.public_key is not None


def test_node_identity_from_env(monkeypatch):
    monkeypatch.setenv("NODE_ID", "som-02")
    node = NodeIdentity.from_env()
    assert node.node_id == "som-02"
```

Create `tests/test_mesh_message.py`:

```python
from return42.mesh.message import MeshMessage, MessageTopic


def test_mesh_message_defaults():
    msg = MeshMessage(source="som-01", destination="som-02", topic=MessageTopic.HEARTBEAT, payload={"rssi": -42})
    assert msg.source == "som-01"
    assert msg.topic == "heartbeat"
    assert msg.payload["rssi"] == -42
    assert msg.msg_id is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_mesh_identity.py tests/test_mesh_message.py -v`

Expected: FAIL with module not found

- [ ] **Step 3: Implement identity and message modules**

Create `src/return42/mesh/identity.py`:

```python
"""Mesh node identity."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass


@dataclass(frozen=True)
class NodeIdentity:
    node_id: str
    public_key: str
    private_key: str | None = None

    @classmethod
    def from_env(cls) -> "NodeIdentity":
        node_id = os.getenv("NODE_ID", "anonymous")
        return cls(
            node_id=node_id,
            public_key=os.getenv("NODE_PUBLIC_KEY", secrets.token_hex(16)),
            private_key=os.getenv("NODE_PRIVATE_KEY"),
        )

    @classmethod
    def generate(cls, node_id: str) -> "NodeIdentity":
        return cls(
            node_id=node_id,
            public_key=secrets.token_hex(16),
            private_key=secrets.token_hex(32),
        )
```

Create `src/return42/mesh/message.py`:

```python
"""Mesh message schema."""

from __future__ import annotations

import time
import uuid
from enum import Enum

from pydantic import BaseModel, Field


class MessageTopic(str, Enum):
    DISCOVERY = "discovery"
    HEARTBEAT = "heartbeat"
    COMMAND = "command"
    TELEMETRY = "telemetry"


class MeshMessage(BaseModel):
    msg_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: str
    destination: str | None = None  # None = broadcast
    topic: MessageTopic
    payload: dict = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)
    signature: str | None = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_mesh_identity.py tests/test_mesh_message.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/return42/mesh/identity.py src/return42/mesh/message.py tests/test_mesh_identity.py tests/test_mesh_message.py
git commit -m "feat: mesh node identity and message schema"
```

---

### Task 3: Mesh Transport Interface and In-Memory Transport

**Files:**
- Create: `src/return42/mesh/transport.py`
- Create: `tests/test_mesh_transport.py`

**Interfaces:**
- Consumes: `MeshMessage`.
- Produces:
  - `MeshTransport` abstract base class with async methods: `start()`, `stop()`, `publish(msg)`, `subscribe(topic, callback)`.
  - `InMemoryTransport`: multi-node in-memory bus for tests.

- [ ] **Step 1: Write failing test**

Create `tests/test_mesh_transport.py`:

```python
import pytest

from return42.mesh.message import MeshMessage, MessageTopic
from return42.mesh.transport import InMemoryTransport


@pytest.mark.asyncio
async def test_in_memory_transport_delivers_message():
    bus = InMemoryTransport()
    await bus.start()
    received = []

    async def handler(msg: MeshMessage):
        received.append(msg)

    await bus.subscribe("heartbeat", handler)
    msg = MeshMessage(source="a", topic=MessageTopic.HEARTBEAT, payload={"seq": 1})
    await bus.publish(msg)
    await bus.stop()

    assert len(received) == 1
    assert received[0].source == "a"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_mesh_transport.py::test_in_memory_transport_delivers_message -v`

Expected: FAIL with module not found

- [ ] **Step 3: Implement transport module**

Create `src/return42/mesh/transport.py`:

```python
"""Mesh transport abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Awaitable, Callable

from .message import MeshMessage


Handler = Callable[[MeshMessage], Awaitable[None]]


class MeshTransport(ABC):
    """Abstract transport for mesh messages."""

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def publish(self, message: MeshMessage) -> None: ...

    @abstractmethod
    async def subscribe(self, topic: str, handler: Handler) -> None: ...


class InMemoryTransport(MeshTransport):
    """In-memory transport for tests and single-process sandboxes."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Handler]] = defaultdict(list)
        self._running = False

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def publish(self, message: MeshMessage) -> None:
        if not self._running:
            raise RuntimeError("Transport not started")
        handlers = self._subscribers.get(message.topic, [])
        for handler in handlers:
            await handler(message)

    async def subscribe(self, topic: str, handler: Handler) -> None:
        self._subscribers[topic].append(handler)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_mesh_transport.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/return42/mesh/transport.py tests/test_mesh_transport.py
git commit -m "feat: mesh transport interface and in-memory transport"
```

---

### Task 4: MQTT Transport Implementation

**Files:**
- Create: `src/return42/mesh/transport_mqtt.py`
- Create: `tests/test_mesh_transport_mqtt.py`

**Interfaces:**
- Consumes: `MeshTransport`, `MeshMessage`, `aiomqtt`.
- Produces:
  - `MqttTransport`: connects to a broker, publishes/subscribes messages serialized as JSON.

- [ ] **Step 1: Write failing test**

Create `tests/test_mesh_transport_mqtt.py`:

```python
import pytest

from return42.mesh.message import MeshMessage, MessageTopic
from return42.mesh.transport_mqtt import MqttTransport


@pytest.mark.asyncio
async def test_mqtt_transport_serialization():
    transport = MqttTransport(host="127.0.0.1", port=1883, node_id="test")
    msg = MeshMessage(source="a", topic=MessageTopic.HEARTBEAT, payload={"seq": 1})
    data = transport._encode(msg)
    decoded = transport._decode(data)
    assert decoded.source == "a"
    assert decoded.topic == MessageTopic.HEARTBEAT
    assert decoded.payload == {"seq": 1}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_mesh_transport_mqtt.py::test_mqtt_transport_serialization -v`

Expected: FAIL with module not found

- [ ] **Step 3: Implement MQTT transport**

Create `src/return42/mesh/transport_mqtt.py`:

```python
"""MQTT-based mesh transport using aiomqtt."""

from __future__ import annotations

import json
import os

from aiomqtt import Client

from .message import MeshMessage
from .transport import Handler, MeshTransport


class MqttTransport(MeshTransport):
    """Mesh transport over MQTT."""

    def __init__(self, host: str | None = None, port: int | None = None, node_id: str | None = None) -> None:
        self._host = host or os.getenv("MQTT_HOST", "127.0.0.1")
        self._port = port or int(os.getenv("MQTT_PORT", "1883"))
        self._node_id = node_id or os.getenv("NODE_ID", "anonymous")
        self._client: Client | None = None
        self._handlers: list[tuple[str, Handler]] = []

    def _encode(self, message: MeshMessage) -> bytes:
        return message.model_dump_json().encode("utf-8")

    def _decode(self, data: bytes) -> MeshMessage:
        return MeshMessage.model_validate_json(data)

    async def start(self) -> None:
        self._client = Client(hostname=self._host, port=self._port)
        await self._client.__aenter__()

    async def stop(self) -> None:
        if self._client is not None:
            await self._client.__aexit__(None, None, None)
            self._client = None

    async def publish(self, message: MeshMessage) -> None:
        if self._client is None:
            raise RuntimeError("Transport not started")
        await self._client.publish(message.topic, self._encode(message))

    async def subscribe(self, topic: str, handler: Handler) -> None:
        if self._client is None:
            raise RuntimeError("Transport not started")
        self._handlers.append((topic, handler))
        await self._client.subscribe(topic)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_mesh_transport_mqtt.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/return42/mesh/transport_mqtt.py tests/test_mesh_transport_mqtt.py
git commit -m "feat: MQTT mesh transport"
```

---

### Task 5: SmeshController Core

**Files:**
- Create: `src/return42/mesh/controller.py`
- Create: `tests/test_mesh_controller.py`

**Interfaces:**
- Consumes: `NodeIdentity`, `MeshMessage`, `MeshTransport`, `InMemoryTransport`, `TelemetryBus`, `EvidenceLogger`.
- Produces:
  - `SmeshController`: `__init__(identity, transport, heartbeat_interval=1.0)`, `start()`, `stop()`, `send(topic, payload, destination=None)`, `on_message(topic, handler)`, `peers` property.

- [ ] **Step 1: Write failing test**

Create `tests/test_mesh_controller.py`:

```python
import pytest

from return42.mesh.controller import SmeshController
from return42.mesh.identity import NodeIdentity
from return42.mesh.message import MessageTopic
from return42.mesh.transport import InMemoryTransport


@pytest.mark.asyncio
async def test_controller_heartbeat_discovery():
    bus = InMemoryTransport()
    node_a = NodeIdentity.generate("som-a")
    node_b = NodeIdentity.generate("som-b")

    ctrl_a = SmeshController(node_a, bus, heartbeat_interval=0.05)
    ctrl_b = SmeshController(node_b, bus, heartbeat_interval=0.05)

    await ctrl_a.start()
    await ctrl_b.start()

    # Wait for heartbeats to exchange
    await asyncio.sleep(0.15)

    assert "som-b" in ctrl_a.peers
    assert "som-a" in ctrl_b.peers

    await ctrl_a.stop()
    await ctrl_b.stop()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_mesh_controller.py::test_controller_heartbeat_discovery -v`

Expected: FAIL with module not found

- [ ] **Step 3: Implement controller**

Create `src/return42/mesh/controller.py`:

```python
"""SOM mesh controller."""

from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable

from return42.observability.telemetry import TelemetryBus, TelemetryEvent, EventLevel

from .identity import NodeIdentity
from .message import MeshMessage, MessageTopic
from .transport import Handler, MeshTransport


MessageHandler = Callable[[MeshMessage], Awaitable[None]]


class SmeshController:
    """Controls a single SOM node in the mesh."""

    def __init__(
        self,
        identity: NodeIdentity,
        transport: MeshTransport,
        heartbeat_interval: float = 1.0,
        telemetry_bus: TelemetryBus | None = None,
    ) -> None:
        self._identity = identity
        self._transport = transport
        self._heartbeat_interval = heartbeat_interval
        self._telemetry = telemetry_bus or TelemetryBus()
        self._peers: dict[str, float] = {}
        self._handlers: dict[str, list[MessageHandler]] = {}
        self._heartbeat_task: asyncio.Task | None = None
        self._running = False

    @property
    def peers(self) -> set[str]:
        return set(self._peers.keys())

    async def start(self) -> None:
        self._running = True
        await self._transport.start()
        await self._transport.subscribe(MessageTopic.HEARTBEAT.value, self._on_heartbeat)
        await self._transport.subscribe(MessageTopic.DISCOVERY.value, self._on_discovery)
        await self._transport.subscribe(MessageTopic.COMMAND.value, self._on_command)
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        await self._announce()

    async def stop(self) -> None:
        self._running = False
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        await self._transport.stop()

    async def send(self, topic: MessageTopic, payload: dict, destination: str | None = None) -> None:
        msg = MeshMessage(
            source=self._identity.node_id,
            destination=destination,
            topic=topic,
            payload=payload,
        )
        await self._transport.publish(msg)
        self._emit_telemetry("mesh.message.sent", {"topic": topic.value, "destination": destination})

    def on_message(self, topic: MessageTopic, handler: MessageHandler) -> None:
        self._handlers.setdefault(topic.value, []).append(handler)

    async def _heartbeat_loop(self) -> None:
        while self._running:
            await self.send(MessageTopic.HEARTBEAT, {"ts": time.time()})
            await asyncio.sleep(self._heartbeat_interval)

    async def _announce(self) -> None:
        await self.send(MessageTopic.DISCOVERY, {"public_key": self._identity.public_key})

    async def _on_heartbeat(self, msg: MeshMessage) -> None:
        if msg.source == self._identity.node_id:
            return
        self._peers[msg.source] = time.time()

    async def _on_discovery(self, msg: MeshMessage) -> None:
        if msg.source == self._identity.node_id:
            return
        self._peers[msg.source] = time.time()
        await self._announce()

    async def _on_command(self, msg: MeshMessage) -> None:
        handlers = self._handlers.get(MessageTopic.COMMAND.value, [])
        for handler in handlers:
            await handler(msg)

    def _emit_telemetry(self, name: str, payload: dict) -> None:
        event = TelemetryEvent(
            name=name,
            source=self._identity.node_id,
            level=EventLevel.INFO,
            payload=payload,
        )
        self._telemetry.publish(event)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_mesh_controller.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/return42/mesh/controller.py tests/test_mesh_controller.py
git commit -m "feat: smesh-controller with discovery and heartbeat"
```

---

### Task 6: Sandbox Integration Test

**Files:**
- Create: `tests/test_mesh_sandbox.py`
- Create: `scripts/run_mesh_sandbox.py`

**Interfaces:**
- Consumes: `SmeshController`, `InMemoryTransport`, `NodeIdentity`.
- Produces:
  - Integration test: 3 nodes discover each other and exchange a command.
  - Script to run a 3-node sandbox.

- [ ] **Step 1: Write failing test**

Create `tests/test_mesh_sandbox.py`:

```python
import asyncio

import pytest

from return42.mesh.controller import SmeshController
from return42.mesh.identity import NodeIdentity
from return42.mesh.message import MessageTopic
from return42.mesh.transport import InMemoryTransport


@pytest.mark.asyncio
async def test_three_node_mesh_command_exchange():
    bus = InMemoryTransport()
    nodes = [NodeIdentity.generate(f"som-{i}") for i in range(3)]
    controllers = [SmeshController(node, bus, heartbeat_interval=0.05) for node in nodes]

    received = []

    async def handler(msg):
        received.append(msg)

    for ctrl in controllers:
        ctrl.on_message(MessageTopic.COMMAND, handler)
        await ctrl.start()

    await asyncio.sleep(0.2)

    # All nodes should see each other
    for ctrl in controllers:
        assert len(ctrl.peers) == 2

    await controllers[0].send(MessageTopic.COMMAND, {"action": "ping"})
    await asyncio.sleep(0.1)

    # Each of the other 2 controllers should receive the command
    assert len(received) == 2

    for ctrl in controllers:
        await ctrl.stop()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_mesh_sandbox.py::test_three_node_mesh_command_exchange -v`

Expected: FAIL with module not found

- [ ] **Step 3: Create sandbox script**

Create `scripts/run_mesh_sandbox.py`:

```python
"""Run a 3-node local mesh sandbox."""

import asyncio

from return42.mesh.controller import SmeshController
from return42.mesh.identity import NodeIdentity
from return42.mesh.message import MessageTopic
from return42.mesh.transport import InMemoryTransport


async def main() -> None:
    bus = InMemoryTransport()
    nodes = [NodeIdentity.generate(f"som-{i}") for i in range(3)]
    controllers = [SmeshController(node, bus, heartbeat_interval=1.0) for node in nodes]

    async def handler(msg):
        print(f"[{msg.destination or 'broadcast'}] {msg.source}: {msg.payload}")

    for ctrl in controllers:
        ctrl.on_message(MessageTopic.COMMAND, handler)
        await ctrl.start()

    print("Sandbox running. Press Ctrl+C to stop.")
    try:
        while True:
            await asyncio.sleep(5)
            for ctrl in controllers:
                print(f"{ctrl._identity.node_id} peers: {ctrl.peers}")
    except asyncio.CancelledError:
        pass
    finally:
        for ctrl in controllers:
            await ctrl.stop()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_mesh_sandbox.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_mesh_sandbox.py scripts/run_mesh_sandbox.py
git commit -m "test: three-node mesh sandbox integration"
```

---

### Task 7: Mesh CLI and Telemetry Integration

**Files:**
- Create: `src/return42/mesh/cli.py`
- Modify: `src/return42/observability/cli.py` to add mesh subcommand
- Create: `tests/test_mesh_cli.py`
- Modify: `README.md` and/or `OBSERVABILITY_RUNBOOK.md`

**Interfaces:**
- Consumes: `SmeshController`, `NodeIdentity`, `InMemoryTransport`, `MqttTransport`, `EvidenceLogger`.
- Produces:
  - CLI subcommand `r42-observe mesh-node --node-id ID --transport memory|mqtt [--heartbeat SEC]`.
  - Evidence logging of mesh events.

- [ ] **Step 1: Write failing test**

Create `tests/test_mesh_cli.py`:

```python
from typer.testing import CliRunner

from return42.mesh.cli import app

runner = CliRunner()


def test_mesh_node_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "mesh-node" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_mesh_cli.py::test_mesh_node_help -v`

Expected: FAIL

- [ ] **Step 3: Implement mesh CLI**

Create `src/return42/mesh/cli.py`:

```python
"""CLI for mesh operations."""

from __future__ import annotations

import asyncio

import typer

from return42.observability.evidence import EvidenceLogger

from .controller import SmeshController
from .identity import NodeIdentity
from .message import MessageTopic
from .transport import InMemoryTransport
from .transport_mqtt import MqttTransport

app = typer.Typer(help="Return42 mesh commands")


@app.command("mesh-node")
def mesh_node(
    node_id: str = typer.Option(..., "--node-id", help="Unique node identifier"),
    transport: str = typer.Option("memory", "--transport", help="memory or mqtt"),
    heartbeat: float = typer.Option(1.0, "--heartbeat", help="Heartbeat interval in seconds"),
    log_dir: str = typer.Option("evidence", "--log-dir", envvar="EVIDENCE_LOG_DIR"),
) -> None:
    """Run a single mesh node."""

    async def run() -> None:
        identity = NodeIdentity.generate(node_id)
        if transport == "memory":
            tx = InMemoryTransport()
        elif transport == "mqtt":
            tx = MqttTransport(node_id=node_id)
        else:
            raise typer.BadParameter(f"Unknown transport: {transport}")

        evidence = EvidenceLogger(log_dir=log_dir)
        controller = SmeshController(identity, tx, heartbeat_interval=heartbeat)

        def log_handler(msg):
            evidence.write(msg)

        controller.on_message(MessageTopic.COMMAND, lambda m: log_handler(m))
        await controller.start()
        typer.echo(f"Node {node_id} running with {transport} transport. Peers: {controller.peers}")
        try:
            while True:
                await asyncio.sleep(5)
                typer.echo(f"Peers: {controller.peers}")
        except asyncio.CancelledError:
            pass
        finally:
            await controller.stop()

    asyncio.run(run())
```

Modify `src/return42/observability/cli.py` to register the mesh subcommand:

```python
from return42.mesh import cli as mesh_cli

app.add_typer(mesh_cli.app, name="mesh")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_mesh_cli.py -v`

Expected: PASS

- [ ] **Step 5: Update docs**

Add a Phase 1 section to `README.md` or `OBSERVABILITY_RUNBOOK.md`:

```markdown
## Phase 1: Local Mesh Baseline

Run a 3-node sandbox:

```bash
python scripts/run_mesh_sandbox.py
```

Run a single node via CLI:

```bash
r42-observe mesh-node --node-id som-01 --transport memory
```
```

- [ ] **Step 6: Commit**

```bash
git add src/return42/mesh/cli.py src/return42/observability/cli.py tests/test_mesh_cli.py README.md
git commit -m "feat: mesh CLI and telemetry integration"
```

---

### Task 8: Final Wiring and Full Suite Verification

**Files:**
- Modify: any remaining imports or wiring
- Test: full suite

**Interfaces:**
- Consumes: All previous modules.
- Produces: A passing full test suite and clean branch.

- [ ] **Step 1: Run full test suite**

Run: `pytest -q`

Expected: all tests PASS

- [ ] **Step 2: Run sandbox script briefly**

Run:

```bash
timeout 3 python scripts/run_mesh_sandbox.py || true
```

Expected: prints peer lists, exits cleanly on timeout.

- [ ] **Step 3: Commit any final fixes**

```bash
git add .
git commit -m "chore: phase 1 final wiring"
```

---

## Self-Review

### Spec coverage

The architecture spec Phase 1 calls for:
- SOM discovery, heartbeat, local messaging → `SmeshController` + `InMemoryTransport`/`MqttTransport`
- `smesh-controller` → implemented
- `mesh-transport` sandbox tests → `test_mesh_transport.py`, `test_mesh_sandbox.py`

### Placeholder scan

No TBD/TODO placeholders. All code is provided.

### Type consistency

- `MeshTransport` async methods return `None`.
- `SmeshController.send` accepts `MessageTopic` enum.
- `NodeIdentity.generate` returns `NodeIdentity`.
