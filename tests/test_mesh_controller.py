import asyncio
import time

import pytest

from return42.mesh.controller import SmeshController
from return42.mesh.identity import NodeIdentity
from return42.mesh.message import MeshMessage, MessageTopic
from return42.mesh.transport import InMemoryTransport
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

    msg = MeshMessage(
        source="som-b",
        destination=None,
        topic=MessageTopic.HEARTBEAT,
        payload={"ts": 1.0},
    )
    await bus.publish(msg)

    assert len(received) == 1
    assert received[0].source == "som-b"

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

    msg = MeshMessage(
        source="som-b",
        destination=None,
        topic=MessageTopic.HEARTBEAT,
        payload={"ts": 1.0},
    )
    await bus.publish(msg)

    # A single published heartbeat must be handled exactly once.
    assert calls == 1
    assert ctrl.peers == {"som-b"}

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
    msg = MeshMessage(
        source="som-b",
        destination=None,
        topic=MessageTopic.COMMAND,
        payload={"action": "ping"},
    )
    await bus.publish(msg)

    assert len(received) == 1
    assert received[0].source == "som-b"

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

    msg = MeshMessage(
        source="som-b",
        destination=None,
        topic=MessageTopic.TELEMETRY,
        payload={"temp": 42.0},
    )
    await bus.publish(msg)

    assert len(received) == 1
    assert received[0].source == "som-b"
    assert received[0].topic == MessageTopic.TELEMETRY

    await ctrl.stop()
