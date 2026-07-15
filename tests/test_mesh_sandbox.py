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
