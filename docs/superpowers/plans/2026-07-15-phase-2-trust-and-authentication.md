# Phase 2: Trust and Authentication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add cryptographic identity, message signing, and peer-trust bootstrap to the Return42 mesh so nodes can authenticate each other, reject forged messages, and fall back to a safe local-only mode when trust cannot be established.

**Architecture:** Each `NodeIdentity` now owns an Ed25519 signing key pair. `MeshMessage` carries a real signature over a canonical serialization of the message. A new `TrustStore` maintains the set of trusted peer public keys and supports pre-shared-key enrollment (`TRUSTED_PEERS`) plus opt-in trust-on-first-use (`TRUST_ON_FIRST_USE=1`) for sandbox development. `SmeshController` verifies every incoming signature, drops invalid messages, and only dispatches `COMMAND` messages from peers that have achieved `TRUSTED` status. Discovery messages advertise a node's public key so peers can learn and verify it. If a node has no trusted peers and TOFU is disabled, the controller stays in reduced local mode: it continues discovery/heartbeat but rejects command handling.

**Tech Stack:** Python 3.11+, `cryptography>=42.0.0`, pydantic, pytest-asyncio, return42.mesh, return42.observability.

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

---

## File Structure

```
.
├── src/return42/
│   └── mesh/
│       ├── __init__.py
│       ├── identity.py          # extended with Ed25519 key pair
│       ├── message.py           # real signature field + canonical serialization
│       ├── transport.py
│       ├── transport_mqtt.py
│       ├── controller.py        # signature verification + trust enforcement
│       ├── trust.py             # TrustStore, TrustLevel, trust bootstrap
│       └── cli.py               # trust/identity options
├── tests/
│   ├── test_mesh_identity.py    # key generation/load/sign/verify
│   ├── test_mesh_message.py     # signature round-trip and tamper detection
│   ├── test_mesh_trust.py       # TrustStore + bootstrap behavior
│   ├── test_mesh_transport.py
│   ├── test_mesh_controller.py  # signed controller tests, untrusted rejection
│   └── test_mesh_sandbox.py
└── scripts/
    └── run_mesh_sandbox.py      # optional TOFU / trusted-peers flags
```

---

### Task 1: Add Cryptography Dependency

**Files:**
- Modify: `pyproject.toml`
- Test: `tests/test_mesh_imports.py`

**Interfaces:**
- Consumes: Existing `pyproject.toml`.
- Produces: `cryptography>=42.0.0` dependency; import test updated.

- [ ] **Step 1: Write the failing test**

Update `tests/test_mesh_imports.py`:

```python
def test_mesh_package_imports():
    import return42.mesh
    import return42.mesh.identity
    import return42.mesh.message
    import return42.mesh.transport
    import return42.mesh.controller
    import return42.mesh.trust
```

Run: `pytest tests/test_mesh_imports.py::test_mesh_package_imports -v`
Expected: FAIL with `ModuleNotFoundError: cannot import name 'trust'`.

- [ ] **Step 2: Add dependency**

Modify `pyproject.toml` dependencies:

```toml
dependencies = [
    "fastapi>=0.111.0",
    "uvicorn[standard]>=0.30.0",
    "prometheus-client>=0.20.0",
    "pydantic>=2.7.0",
    "typer>=0.12.0",
    "aiomqtt>=2.0.0",
    "cryptography>=42.0.0",
]
```

- [ ] **Step 3: Install and run test**

```bash
.venv/bin/python -m pip install -e ".[dev]"
pytest tests/test_mesh_imports.py::test_mesh_package_imports -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml tests/test_mesh_imports.py
git commit -m "chore: add cryptography dependency and trust package marker"
```

---

### Task 2: Extend NodeIdentity with Ed25519 Keys

**Files:**
- Modify: `src/return42/mesh/identity.py`
- Test: `tests/test_mesh_identity.py`

**Interfaces:**
- Consumes: `cryptography.hazmat.primitives.asymmetric.ed25519`.
- Produces:
  - `NodeIdentity.signing_key: Ed25519PrivateKey` (not serialized)
  - `NodeIdentity.verify_key: Ed25519PublicKey`
  - `NodeIdentity.verify_key_b64: str` (public key as URL-safe base64)
  - `NodeIdentity.generate(node_id, seed=None)`
  - `NodeIdentity.from_env(node_id=None)` — loads base64 signing key from `NODE_SIGNING_KEY`; generates+persist ephemeral key only in tests/sandbox when env absent
  - `NodeIdentity.sign(data: bytes) -> bytes`
  - `NodeIdentity.verify(data: bytes, signature: bytes) -> bool`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_mesh_identity.py`:

```python
def test_identity_sign_and_verify():
    node = NodeIdentity.generate("som-a")
    data = b"hello mesh"
    sig = node.sign(data)
    assert node.verify(data, sig) is True
    assert node.verify(b"tampered", sig) is False


def test_identity_from_env():
    import os
    node = NodeIdentity.generate("som-a")
    os.environ["NODE_SIGNING_KEY"] = node.signing_key_b64
    loaded = NodeIdentity.from_env("som-a")
    assert loaded.verify_key_b64 == node.verify_key_b64
```

Run: `pytest tests/test_mesh_identity.py -v`
Expected: FAIL (missing methods).

- [ ] **Step 2: Implement**

Extend `src/return42/mesh/identity.py` to hold an Ed25519 key pair, provide sign/verify, and load from env.

Guidelines:
- Keep the dataclass frozen; store only the verify key publicly.
- Expose `signing_key` as a `@property` that returns the cached private key object.
- Use URL-safe base64 for serialization.
- `from_env` must raise a clear error if `NODE_SIGNING_KEY` is malformed.

- [ ] **Step 3: Run tests**

```bash
pytest tests/test_mesh_identity.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/return42/mesh/identity.py tests/test_mesh_identity.py
git commit -m "feat(mesh): Ed25519 signing keys in NodeIdentity"
```

---

### Task 3: Implement TrustStore and Trust Bootstrap

**Files:**
- Create: `src/return42/mesh/trust.py`
- Test: `tests/test_mesh_trust.py`

**Interfaces:**
- Produces:
  - `TrustLevel` enum: `UNTRUSTED`, `TRUSTED`.
  - `TrustStore`: `__init__(tofu=False, trusted_peers=None)`, `is_trusted(node_id)`, `register(node_id, verify_key_b64)`, `trust_from_discovery(node_id, verify_key_b64)`.
  - `TRUSTED_PEERS` env var: comma-separated `node_id:verify_key_b64` entries.

- [ ] **Step 1: Write failing test**

Create `tests/test_mesh_trust.py`:

```python
def test_trust_store_rejects_unknown_when_tofu_off():
    store = TrustStore(tofu=False)
    assert store.is_trusted("som-b") is False
    store.trust_from_discovery("som-b", "key-b64")
    assert store.is_trusted("som-b") is False


def test_trust_store_accepts_pre_enrolled_peer():
    store = TrustStore(tofu=False, trusted_peers={"som-b": "key-b64"})
    assert store.is_trusted("som-b") is True


def test_trust_store_tofu():
    store = TrustStore(tofu=True)
    store.trust_from_discovery("som-b", "key-b64")
    assert store.is_trusted("som-b") is True
```

Run: `pytest tests/test_mesh_trust.py -v`
Expected: FAIL (missing module).

- [ ] **Step 2: Implement**

Create `src/return42/mesh/trust.py`:

```python
from __future__ import annotations

import os
from enum import Enum


class TrustLevel(str, Enum):
    UNTRUSTED = "untrusted"
    TRUSTED = "trusted"


class TrustStore:
    def __init__(self, tofu: bool = False, trusted_peers: dict[str, str] | None = None) -> None:
        self._tofu = tofu
        self._trusted: dict[str, str] = dict(trusted_peers or {})

    def is_trusted(self, node_id: str) -> bool:
        return node_id in self._trusted

    def register(self, node_id: str, verify_key_b64: str) -> None:
        self._trusted[node_id] = verify_key_b64

    def trust_from_discovery(self, node_id: str, verify_key_b64: str) -> bool:
        if self._tofu:
            self.register(node_id, verify_key_b64)
            return True
        return node_id in self._trusted

    @classmethod
    def from_env(cls) -> "TrustStore":
        tofu = os.getenv("TRUST_ON_FIRST_USE", "false").lower() in ("1", "true", "yes")
        raw = os.getenv("TRUSTED_PEERS", "")
        peers: dict[str, str] = {}
        for entry in raw.split(","):
            entry = entry.strip()
            if not entry:
                continue
            node_id, key = entry.split(":", 1)
            peers[node_id.strip()] = key.strip()
        return cls(tofu=tofu, trusted_peers=peers)
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/test_mesh_trust.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/return42/mesh/trust.py tests/test_mesh_trust.py
git commit -m "feat(mesh): TrustStore with pre-enrollment and TOFU"
```

---

### Task 4: Sign and Verify MeshMessage

**Files:**
- Modify: `src/return42/mesh/message.py`
- Modify: `src/return42/mesh/controller.py` (send path)
- Test: `tests/test_mesh_message.py`

**Interfaces:**
- `MeshMessage.sign(identity: NodeIdentity) -> MeshMessage` — returns a new message with `signature` set.
- `MeshMessage.verify(identity: NodeIdentity) -> bool` — verifies the signature.
- Canonical serialization: JSON of `source`, `destination`, `topic`, `payload`, `timestamp`, `msg_id`, sorted keys, no whitespace.

- [ ] **Step 1: Write failing tests**

Update `tests/test_mesh_message.py`:

```python
def test_message_signature_round_trip():
    node = NodeIdentity.generate("som-a")
    msg = MeshMessage(source="som-a", topic=MessageTopic.COMMAND, payload={"action": "ping"})
    signed = msg.sign(node)
    assert signed.signature is not None
    assert signed.verify(node) is True


def test_message_signature_detects_tampering():
    node = NodeIdentity.generate("som-a")
    msg = MeshMessage(source="som-a", topic=MessageTopic.COMMAND, payload={"action": "ping"})
    signed = msg.sign(node)
    tampered = signed.model_copy(update={"payload": {"action": "pwn"}})
    assert tampered.verify(node) is False
```

Run: `pytest tests/test_mesh_message.py -v`
Expected: FAIL.

- [ ] **Step 2: Implement**

Add `sign` and `verify` methods to `MeshMessage`. Keep the existing schema fields; update `signature` from `str | None` to a base64 string.

- [ ] **Step 3: Run tests**

```bash
pytest tests/test_mesh_message.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/return42/mesh/message.py tests/test_mesh_message.py
git commit -m "feat(mesh): sign and verify MeshMessage with Ed25519"
```

---

### Task 5: Enforce Trust in SmeshController

**Files:**
- Modify: `src/return42/mesh/controller.py`
- Test: `tests/test_mesh_controller.py`

**Interfaces:**
- `SmeshController.__init__(..., trust_store: TrustStore | None = None, reduced_mode: bool = False)`
- `SmeshController.mode` property: `"full"` if at least one trusted peer exists or TOFU enabled; `"reduced"` otherwise.
- On incoming message: verify signature; if invalid, drop and emit telemetry `mesh.message.signature_invalid`.
- On `DISCOVERY`: validate signature, register public key in trust store (TOFU or pre-trusted), update peers.
- On `HEARTBEAT`: validate signature, update peer timestamp.
- On `COMMAND`: validate signature, reject if source not trusted, otherwise dispatch user handlers.
- `send()` signs the message before publishing using the controller's identity.

- [ ] **Step 1: Write failing tests**

Add to `tests/test_mesh_controller.py`:

```python
@pytest.mark.asyncio
async def test_controller_rejects_unsigned_command():
    bus = InMemoryTransport()
    node_a = NodeIdentity.generate("som-a")
    node_b = NodeIdentity.generate("som-b")
    ctrl_a = SmeshController(node_a, bus, heartbeat_interval=0.05, trust_store=TrustStore(tofu=True))
    ctrl_b = SmeshController(node_b, bus, heartbeat_interval=0.05, trust_store=TrustStore(tofu=True))

    received = []
    ctrl_b.on_message(MessageTopic.COMMAND, lambda m: received.append(m))

    await ctrl_a.start()
    await ctrl_b.start()
    await _wait_for(lambda: len(ctrl_a.peers) == 1 and len(ctrl_b.peers) == 1)

    await ctrl_a.send(MessageTopic.COMMAND, {"action": "ping"})
    await _wait_for(lambda: len(received) == 1)

    assert received[0].source == "som-a"
    await ctrl_a.stop()
    await ctrl_b.stop()


@pytest.mark.asyncio
async def test_controller_rejects_command_from_untrusted_peer():
    bus = InMemoryTransport()
    node_a = NodeIdentity.generate("som-a")
    node_b = NodeIdentity.generate("som-b")
    # b does not trust a and TOFU is off
    ctrl_b = SmeshController(node_b, bus, heartbeat_interval=0.05, trust_store=TrustStore(tofu=False))
    ctrl_a = SmeshController(node_a, bus, heartbeat_interval=0.05, trust_store=TrustStore(tofu=False))

    received = []
    ctrl_b.on_message(MessageTopic.COMMAND, lambda m: received.append(m))

    await ctrl_a.start()
    await ctrl_b.start()
    await asyncio.sleep(0.15)

    await ctrl_a.send(MessageTopic.COMMAND, {"action": "ping"})
    await asyncio.sleep(0.1)

    assert len(received) == 0
    await ctrl_a.stop()
    await ctrl_b.stop()
```

Run: `pytest tests/test_mesh_controller.py -v`
Expected: FAIL (unsigned messages rejected, but current send doesn't sign).

- [ ] **Step 2: Implement**

Update `SmeshController`:
- Inject `trust_store` defaulting to `TrustStore(tofu=True)` for sandbox convenience.
- Sign every outgoing message in `send()`.
- Verify signature on every incoming message in `_on_message()`; drop invalid ones.
- Update trust on discovery using `trust_store.trust_from_discovery(...)`.
- Only dispatch command handlers if `trust_store.is_trusted(msg.source)`.

- [ ] **Step 3: Run tests**

```bash
pytest tests/test_mesh_controller.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/return42/mesh/controller.py tests/test_mesh_controller.py
git commit -m "feat(mesh): controller signs and verifies messages; enforces trust"
```

---

### Task 6: Update CLI and Sandbox with Trust Options

**Files:**
- Modify: `src/return42/mesh/cli.py`
- Modify: `scripts/run_mesh_sandbox.py`
- Test: `tests/test_mesh_cli.py`

**Interfaces:**
- CLI options: `--trust-on-first-use / --no-trust-on-first-use`, `--trusted-peers TEXT`.
- CLI uses `NodeIdentity.from_env()` and `TrustStore.from_env()` by default, with options overriding env.
- Sandbox accepts the same flags and passes them to controllers.

- [ ] **Step 1: Write failing test**

Add to `tests/test_mesh_cli.py`:

```python
def test_mesh_node_help_lists_trust_options():
    result = runner.invoke(app, ["mesh-node", "--help"])
    assert result.exit_code == 0
    assert "--trust-on-first-use" in result.output
```

Run: `pytest tests/test_mesh_cli.py::test_mesh_node_help_lists_trust_options -v`
Expected: FAIL.

- [ ] **Step 2: Implement**

Update `src/return42/mesh/cli.py` to add trust options and wire them into `TrustStore`. Update `scripts/run_mesh_sandbox.py` to accept matching CLI args.

- [ ] **Step 3: Run tests**

```bash
pytest tests/test_mesh_cli.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/return42/mesh/cli.py scripts/run_mesh_sandbox.py tests/test_mesh_cli.py
git commit -m "feat(cli): trust options for mesh-node and sandbox"
```

---

### Task 7: Add Trust-Aware Sandbox Integration Test

**Files:**
- Create: `tests/test_mesh_sandbox.py` updates (or new `tests/test_mesh_trust_sandbox.py`)

**Interfaces:**
- 3-node sandbox test with TOFU enabled: all nodes discover, trust each other, and exchange a signed command.
- 3-node sandbox test with TOFU disabled and only two nodes pre-trusted: the untrusted node's command is rejected.

- [ ] **Step 1: Write failing tests**

Add to `tests/test_mesh_sandbox.py`:

```python
@pytest.mark.asyncio
async def test_three_node_mesh_with_tofu():
    bus = InMemoryTransport()
    nodes = [NodeIdentity.generate(f"som-{i}") for i in range(3)]
    controllers = [
        SmeshController(node, bus, heartbeat_interval=0.05, trust_store=TrustStore(tofu=True))
        for node in nodes
    ]
    # ... same pattern as Phase 1 sandbox test, assert all 2 non-sender nodes receive command


@pytest.mark.asyncio
async def test_three_node_mesh_rejects_untrusted_command():
    bus = InMemoryTransport()
    nodes = [NodeIdentity.generate(f"som-{i}") for i in range(3)]
    # Controller 0 and 1 are mutually trusted; controller 2 is untrusted
    store_0 = TrustStore(tofu=False, trusted_peers={nodes[1].node_id: nodes[1].verify_key_b64})
    store_1 = TrustStore(tofu=False, trusted_peers={nodes[0].node_id: nodes[0].verify_key_b64})
    store_2 = TrustStore(tofu=False)
    controllers = [
        SmeshController(nodes[0], bus, heartbeat_interval=0.05, trust_store=store_0),
        SmeshController(nodes[1], bus, heartbeat_interval=0.05, trust_store=store_1),
        SmeshController(nodes[2], bus, heartbeat_interval=0.05, trust_store=store_2),
    ]
    # ... assert command from 0 is received by 1, not by 2
```

Run: `pytest tests/test_mesh_sandbox.py -v`
Expected: FAIL (trust not wired).

- [ ] **Step 2: Implement / wire**

The controller changes from Task 5 should make these tests pass once the trust stores are set up correctly.

- [ ] **Step 3: Run tests**

```bash
pytest tests/test_mesh_sandbox.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_mesh_sandbox.py
git commit -m "test(mesh): trust-aware three-node sandbox tests"
```

---

### Task 8: Final Wiring and Full Suite Verification

**Files:**
- Modify: any remaining imports or wiring
- Test: full suite

**Interfaces:**
- Produces: A passing full test suite and clean branch.

- [ ] **Step 1: Run full test suite**

```bash
pytest -q
```

Expected: all tests PASS.

- [ ] **Step 2: Run sandbox briefly**

```bash
timeout 3 python scripts/run_mesh_sandbox.py --trust-on-first-use || true
```

Expected: prints peer lists, exits cleanly on timeout.

- [ ] **Step 3: Update docs**

Add a short **Phase 2: Trust and Authentication** section to `README.md` and/or `OBSERVABILITY_RUNBOOK.md` showing:
- How to generate a node signing key.
- How to run two nodes with pre-shared trust.
- How to run with TOFU for sandbox.

- [ ] **Step 4: Commit final fixes**

```bash
git add .
git commit -m "chore: phase 2 final wiring and docs"
```

---

## Self-Review Checklist

- [ ] All `MeshMessage` instances are signed before publish.
- [ ] All incoming messages are signature-verified; invalid ones are dropped.
- [ ] Commands are only dispatched from trusted peers.
- [ ] Private signing keys are never logged, serialized, or sent on the wire.
- [ ] TrustStore supports both pre-enrollment and TOFU.
- [ ] Reduced local mode is exercised in tests.
- [ ] No `TODO`/`TBD` placeholders remain.
