import asyncio

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
