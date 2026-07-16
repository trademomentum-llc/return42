"""Tests for mesh observability instrumentation."""

from __future__ import annotations

import pytest
from prometheus_client import CollectorRegistry

from return42.mesh.controller import SmeshController
from return42.mesh.identity import NodeIdentity
from return42.mesh.message import MeshMessage, MessageTopic
from return42.mesh.transport import InMemoryTransport
from return42.observability.metrics import MetricsRegistry
from return42.observability.telemetry import TelemetryBus
from tests.conftest import _wait_for


@pytest.mark.asyncio
async def test_sent_message_metric():
    bus = InMemoryTransport()
    node = NodeIdentity.generate("som-a")
    registry = MetricsRegistry(registry=CollectorRegistry())
    ctrl = SmeshController(node, bus, registry=registry)

    await ctrl.start()
    try:
        await ctrl.send(MessageTopic.COMMAND, {"action": "ping"})
    finally:
        await ctrl.stop()

    samples = registry.get_sample_values("mesh_messages_sent_total")
    assert any(
        sample_name == "mesh_messages_sent_total" and dict(labels).get("topic") == "command"
        for sample_name, labels in samples
    )


@pytest.mark.asyncio
async def test_received_message_metric():
    bus = InMemoryTransport()
    node = NodeIdentity.generate("som-a")
    registry = MetricsRegistry(registry=CollectorRegistry())
    ctrl = SmeshController(node, bus, registry=registry)

    sender = NodeIdentity.generate("som-b")
    ctrl._trust_store.register(sender.node_id, sender.public_key)

    await ctrl.start()
    try:
        msg = MeshMessage(
            source=sender.node_id,
            destination=None,
            topic=MessageTopic.HEARTBEAT,
            payload={"ts": 1.0},
        ).sign(sender)
        await bus.publish(msg)
    finally:
        await ctrl.stop()

    samples = registry.get_sample_values("mesh_messages_received_total")
    assert any(
        sample_name == "mesh_messages_received_total" and dict(labels).get("topic") == "heartbeat"
        for sample_name, labels in samples
    )


@pytest.mark.asyncio
async def test_peer_count_gauge():
    bus = InMemoryTransport()
    node_a = NodeIdentity.generate("som-a")
    node_b = NodeIdentity.generate("som-b")
    registry_a = MetricsRegistry(registry=CollectorRegistry())
    registry_b = MetricsRegistry(registry=CollectorRegistry())
    ctrl_a = SmeshController(node_a, bus, heartbeat_interval=0.05, registry=registry_a)
    ctrl_b = SmeshController(node_b, bus, heartbeat_interval=0.05, registry=registry_b)

    await ctrl_a.start()
    await ctrl_b.start()
    try:
        await _wait_for(lambda: "som-b" in ctrl_a.peers and "som-a" in ctrl_b.peers)

        samples_a = registry_a.get_sample_values("mesh_peers_count")
        values_a = [v for _, v in samples_a.items()]
        assert any(v == 1.0 for v in values_a)
    finally:
        await ctrl_a.stop()
        await ctrl_b.stop()


@pytest.mark.asyncio
async def test_received_telemetry_event():
    bus = InMemoryTransport()
    node = NodeIdentity.generate("som-a")
    telemetry = TelemetryBus()
    ctrl = SmeshController(node, bus, telemetry_bus=telemetry)

    sender = NodeIdentity.generate("som-b")
    ctrl._trust_store.register(sender.node_id, sender.public_key)

    await ctrl.start()
    try:
        msg = MeshMessage(
            source=sender.node_id,
            destination=None,
            topic=MessageTopic.COMMAND,
            payload={"action": "ping"},
        ).sign(sender)
        await bus.publish(msg)
    finally:
        await ctrl.stop()

    events = telemetry.events("mesh.message.received")
    assert len(events) == 1
    assert events[0].payload["topic"] == "command"
    assert events[0].payload["source"] == sender.node_id
