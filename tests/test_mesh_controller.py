import asyncio
import time

import pytest
from prometheus_client import CollectorRegistry

from return42.mesh.controller import SmeshController
from return42.mesh.identity import NodeIdentity
from return42.mesh.message import MeshMessage, MessageTopic
from return42.mesh.transport import InMemoryTransport
from return42.mesh.trust import TrustStore
from return42.observability.metrics import MetricsRegistry
from return42.observability.telemetry import TelemetryBus
from tests.conftest import _wait_for


@pytest.mark.asyncio
async def test_controller_heartbeat_discovery():
    bus = InMemoryTransport()
    node_a = NodeIdentity.generate("som-a")
    node_b = NodeIdentity.generate("som-b")

    ctrl_a = SmeshController(node_a, bus, heartbeat_interval=0.05)
    ctrl_b = SmeshController(node_b, bus, heartbeat_interval=0.05)

    await ctrl_a.start()
    await ctrl_b.start()

    try:
        # Wait for heartbeats to exchange (deterministic).
        await _wait_for(lambda: "som-b" in ctrl_a.peers and "som-a" in ctrl_b.peers)

        assert "som-b" in ctrl_a.peers
        assert "som-a" in ctrl_b.peers
    finally:
        await ctrl_a.stop()
        await ctrl_b.stop()


@pytest.mark.asyncio
async def test_user_heartbeat_handler_is_dispatched():
    bus = InMemoryTransport()
    node = NodeIdentity.generate("som-a")
    ctrl = SmeshController(node, bus)

    received = []

    async def handler(msg: MeshMessage) -> None:
        received.append(msg)

    ctrl.on_message(MessageTopic.HEARTBEAT, handler)
    await ctrl.start()

    sender = NodeIdentity.generate("som-b")
    ctrl._trust_store.register(sender.node_id, sender.public_key)
    msg = MeshMessage(
        source=sender.node_id,
        destination=None,
        topic=MessageTopic.HEARTBEAT,
        payload={"ts": 1.0},
    ).sign(sender)
    await bus.publish(msg)

    assert len(received) == 1
    assert received[0].source == sender.node_id

    await ctrl.stop()


@pytest.mark.asyncio
async def test_restart_does_not_duplicate_subscriptions():
    bus = InMemoryTransport()
    node = NodeIdentity.generate("som-a")
    ctrl = SmeshController(node, bus)

    await ctrl.start()
    await ctrl.stop()

    calls = 0
    original_on_message = ctrl._on_message

    async def wrapped_on_message(msg: MeshMessage) -> None:
        nonlocal calls
        if msg.source != node.node_id:
            calls += 1
        await original_on_message(msg)

    ctrl._on_message = wrapped_on_message
    await ctrl.start()

    sender = NodeIdentity.generate("som-b")
    ctrl._trust_store.register(sender.node_id, sender.public_key)
    msg = MeshMessage(
        source=sender.node_id,
        destination=None,
        topic=MessageTopic.HEARTBEAT,
        payload={"ts": 1.0},
    ).sign(sender)
    await bus.publish(msg)

    # A single published heartbeat must be handled exactly once.
    assert calls == 1
    assert ctrl.peers == {sender.node_id}

    await ctrl.stop()


@pytest.mark.asyncio
async def test_start_raises_when_already_running():
    bus = InMemoryTransport()
    node = NodeIdentity.generate("som-a")
    ctrl = SmeshController(node, bus)

    await ctrl.start()
    try:
        with pytest.raises(RuntimeError, match="Controller already started"):
            await ctrl.start()
    finally:
        await ctrl.stop()


@pytest.mark.asyncio
async def test_stop_is_idempotent():
    bus = InMemoryTransport()
    node = NodeIdentity.generate("som-a")
    ctrl = SmeshController(node, bus)

    await ctrl.start()
    await ctrl.stop()
    # A second stop should be a no-op, not raise.
    await ctrl.stop()


@pytest.mark.asyncio
async def test_start_failure_invokes_stop(monkeypatch):
    bus = InMemoryTransport()
    node = NodeIdentity.generate("som-a")
    ctrl = SmeshController(node, bus)

    async def failing_start() -> None:
        raise RuntimeError("transport start failed")

    monkeypatch.setattr(bus, "start", failing_start)

    stop_calls = []
    original_stop = bus.stop

    async def spied_stop() -> None:
        stop_calls.append(1)
        await original_stop()

    monkeypatch.setattr(bus, "stop", spied_stop)

    with pytest.raises(RuntimeError, match="transport start failed"):
        await ctrl.start()

    assert len(stop_calls) == 1
    assert not ctrl._running


@pytest.mark.asyncio
async def test_sync_user_handler_is_dispatched():
    bus = InMemoryTransport()
    node = NodeIdentity.generate("som-a")
    ctrl = SmeshController(node, bus)

    received = []
    ctrl.on_message(MessageTopic.COMMAND, lambda msg: received.append(msg))

    await ctrl.start()
    sender = NodeIdentity.generate("som-b")
    ctrl._trust_store.register(sender.node_id, sender.public_key)
    msg = MeshMessage(
        source=sender.node_id,
        destination=None,
        topic=MessageTopic.COMMAND,
        payload={"action": "ping"},
    ).sign(sender)
    await bus.publish(msg)

    assert len(received) == 1
    assert received[0].source == sender.node_id

    await ctrl.stop()


@pytest.mark.asyncio
async def test_peer_expires_after_timeout():
    bus = InMemoryTransport()
    node = NodeIdentity.generate("som-a")
    heartbeat_interval = 0.05
    peer_timeout = 0.1
    ctrl = SmeshController(node, bus, heartbeat_interval=heartbeat_interval, peer_timeout=peer_timeout)

    await ctrl.start()
    try:
        # Inject a peer with a stale timestamp.
        ctrl._peers["stale-node"] = time.time() - 2 * peer_timeout
        await _wait_for(lambda: "stale-node" not in ctrl._peers, timeout=0.5)
        assert "stale-node" not in ctrl.peers
    finally:
        await ctrl.stop()


@pytest.mark.asyncio
async def test_directed_command_only_delivered_to_destination():
    bus = InMemoryTransport()
    node_a = NodeIdentity.generate("som-a")
    node_b = NodeIdentity.generate("som-b")

    ctrl_a = SmeshController(node_a, bus, heartbeat_interval=0.05)
    ctrl_b = SmeshController(node_b, bus, heartbeat_interval=0.05)

    received_by_a = []
    received_by_b = []

    async def handler_a(msg: MeshMessage) -> None:
        received_by_a.append(msg)

    async def handler_b(msg: MeshMessage) -> None:
        received_by_b.append(msg)

    ctrl_a.on_message(MessageTopic.COMMAND, handler_a)
    ctrl_b.on_message(MessageTopic.COMMAND, handler_b)

    await ctrl_a.start()
    await ctrl_b.start()

    try:
        await ctrl_a.send(
            MessageTopic.COMMAND,
            {"action": "ping"},
            destination=node_b.node_id,
        )

        await _wait_for(lambda: len(received_by_b) == 1, timeout=0.5)
        assert len(received_by_b) == 1
        assert received_by_b[0].source == node_a.node_id
        assert len(received_by_a) == 0
    finally:
        await ctrl_a.stop()
        await ctrl_b.stop()


@pytest.mark.asyncio
async def test_controller_subscribes_to_all_topics():
    bus = InMemoryTransport()
    node = NodeIdentity.generate("som-a")
    ctrl = SmeshController(node, bus)

    subscribed_topics = []
    original_subscribe = bus.subscribe

    async def spied_subscribe(topic: str, handler) -> None:
        subscribed_topics.append(topic)
        await original_subscribe(topic, handler)

    bus.subscribe = spied_subscribe

    await ctrl.start()
    try:
        expected = {topic.value for topic in MessageTopic}
        assert set(subscribed_topics) == expected
    finally:
        await ctrl.stop()


@pytest.mark.asyncio
async def test_telemetry_message_dispatches_user_handler():
    bus = InMemoryTransport()
    node = NodeIdentity.generate("som-a")
    ctrl = SmeshController(node, bus)

    received = []

    async def handler(msg: MeshMessage) -> None:
        received.append(msg)

    ctrl.on_message(MessageTopic.TELEMETRY, handler)
    await ctrl.start()

    sender = NodeIdentity.generate("som-b")
    ctrl._trust_store.register(sender.node_id, sender.public_key)
    msg = MeshMessage(
        source=sender.node_id,
        destination=None,
        topic=MessageTopic.TELEMETRY,
        payload={"temp": 42.0},
    ).sign(sender)
    await bus.publish(msg)

    assert len(received) == 1
    assert received[0].source == sender.node_id
    assert received[0].topic == MessageTopic.TELEMETRY

    await ctrl.stop()



@pytest.mark.asyncio
async def test_controller_accepts_signed_command_after_discovery():
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



@pytest.mark.asyncio
async def test_controller_drops_unsigned_heartbeat_and_records_metrics():
    bus = InMemoryTransport()
    node = NodeIdentity.generate("som-a")
    registry = MetricsRegistry(registry=CollectorRegistry())
    telemetry = TelemetryBus()
    ctrl = SmeshController(node, bus, registry=registry, telemetry_bus=telemetry)

    received = []
    ctrl.on_message(MessageTopic.HEARTBEAT, lambda m: received.append(m))
    await ctrl.start()

    msg = MeshMessage(
        source="som-b",
        destination=None,
        topic=MessageTopic.HEARTBEAT,
        payload={"ts": 1.0},
    )
    await bus.publish(msg)
    await asyncio.sleep(0.05)

    assert len(received) == 0
    failure_samples = registry.get_sample_values("mesh_signature_failures_total")
    assert sum(
        v for (name, _), v in failure_samples.items() if name == "mesh_signature_failures_total"
    ) == 1.0
    verification_samples = registry.get_sample_values("mesh_signature_verifications_total")
    invalid = {
        k: v
        for k, v in verification_samples.items()
        if k[0] == "mesh_signature_verifications_total"
        and dict(k[1]).get("valid") == "false"
    }
    assert sum(invalid.values()) == 1.0
    assert any(e.name == "mesh.message.signature_invalid" for e in telemetry.events())

    await ctrl.stop()


@pytest.mark.asyncio
async def test_controller_command_rejection_records_metric_and_telemetry():
    bus = InMemoryTransport()
    node = NodeIdentity.generate("som-a")
    sender = NodeIdentity.generate("som-b")
    registry = MetricsRegistry(registry=CollectorRegistry())
    telemetry = TelemetryBus()
    ctrl = SmeshController(
        node,
        bus,
        registry=registry,
        telemetry_bus=telemetry,
        trust_store=TrustStore(tofu=False),
    )

    received = []
    ctrl.on_message(MessageTopic.COMMAND, lambda m: received.append(m))
    await ctrl.start()

    # Discover the sender so the controller knows its key, but keep TOFU off
    # so the peer remains untrusted.
    discovery = MeshMessage(
        source=sender.node_id,
        destination=None,
        topic=MessageTopic.DISCOVERY,
        payload={"public_key": sender.public_key},
    ).sign(sender)
    await bus.publish(discovery)
    await asyncio.sleep(0.05)

    assert not ctrl._trust_store.is_trusted(sender.node_id)

    msg = MeshMessage(
        source=sender.node_id,
        destination=None,
        topic=MessageTopic.COMMAND,
        payload={"action": "ping"},
    ).sign(sender)
    await bus.publish(msg)
    await asyncio.sleep(0.05)

    assert len(received) == 0
    rejection_samples = registry.get_sample_values("mesh_command_rejections_total")
    assert sum(
        v for (name, _), v in rejection_samples.items() if name == "mesh_command_rejections_total"
    ) == 1.0
    rejected_events = telemetry.events("mesh.command.rejected")
    assert len(rejected_events) == 1
    assert rejected_events[0].payload["reason"] == "untrusted"

    await ctrl.stop()


@pytest.mark.asyncio
async def test_controller_mode_reflects_trust_state():
    bus = InMemoryTransport()
    node = NodeIdentity.generate("som-a")

    ctrl_tofu = SmeshController(node, bus, trust_store=TrustStore(tofu=True))
    assert ctrl_tofu.mode == "full"

    ctrl_empty = SmeshController(node, bus, trust_store=TrustStore(tofu=False))
    assert ctrl_empty.mode == "reduced"

    ctrl_pretrusted = SmeshController(
        node,
        bus,
        trust_store=TrustStore(tofu=False, trusted_peers={"som-b": "key"}),
    )
    assert ctrl_pretrusted.mode == "full"

    ctrl_forced_reduced = SmeshController(
        node, bus, trust_store=TrustStore(tofu=True), reduced_mode=True
    )
    assert ctrl_forced_reduced.mode == "reduced"


@pytest.mark.asyncio
async def test_controller_discovery_registers_trust_with_tofu():
    bus = InMemoryTransport()
    node = NodeIdentity.generate("som-a")
    sender = NodeIdentity.generate("som-b")
    registry = MetricsRegistry(registry=CollectorRegistry())
    telemetry = TelemetryBus()
    ctrl = SmeshController(
        node,
        bus,
        registry=registry,
        telemetry_bus=telemetry,
        trust_store=TrustStore(tofu=True),
    )

    await ctrl.start()

    msg = MeshMessage(
        source=sender.node_id,
        destination=None,
        topic=MessageTopic.DISCOVERY,
        payload={"public_key": sender.public_key},
    ).sign(sender)
    await bus.publish(msg)
    await asyncio.sleep(0.05)

    assert ctrl._trust_store.is_trusted(sender.node_id)
    trusted_events = telemetry.events("mesh.peer.trusted")
    assert len(trusted_events) == 1
    assert trusted_events[0].payload["peer_id"] == sender.node_id

    gauge_samples = registry.get_sample_values("mesh_peer_trust_state")
    trusted_sample = {
        k: v
        for k, v in gauge_samples.items()
        if k[0] == "mesh_peer_trust_state"
        and dict(k[1]).get("node_id") == sender.node_id
        and dict(k[1]).get("level") == "trusted"
    }
    assert sum(trusted_sample.values()) == 1.0

    await ctrl.stop()
