import asyncio

import pytest

from return42.mesh.controller import SmeshController
from return42.mesh.identity import NodeIdentity
from return42.mesh.message import MeshMessage, MessageTopic
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
    original_on_heartbeat = ctrl._on_heartbeat

    async def wrapped_on_heartbeat(msg: MeshMessage) -> None:
        nonlocal calls
        calls += 1
        await original_on_heartbeat(msg)

    ctrl._on_heartbeat = wrapped_on_heartbeat
    await ctrl.start()

    # There should be exactly one subscription after the restart.
    assert bus._subscribers[MessageTopic.HEARTBEAT.value].count(ctrl._on_heartbeat) == 1

    msg = MeshMessage(
        source="som-b",
        destination=None,
        topic=MessageTopic.HEARTBEAT,
        payload={"ts": 1.0},
    )
    await bus.publish(msg)

    assert calls == 1
    assert ctrl.peers == {"som-b"}

    await ctrl.stop()
