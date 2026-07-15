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

    received_by_node = {node.node_id: [] for node in nodes}

    def make_handler(node_id):
        async def handler(msg):
            received_by_node[node_id].append(msg)
        return handler

    try:
        for ctrl in controllers:
            ctrl.on_message(MessageTopic.COMMAND, make_handler(ctrl._identity.node_id))
            await ctrl.start()

        await asyncio.sleep(0.2)

        # All nodes should see each other
        for ctrl in controllers:
            assert len(ctrl.peers) == 2

        sender = controllers[0]
        await sender.send(MessageTopic.COMMAND, {"action": "ping"})
        await asyncio.sleep(0.1)

        # Sender should not receive its own command; the other two should
        assert len(received_by_node[sender._identity.node_id]) == 0
        for ctrl in controllers[1:]:
            assert len(received_by_node[ctrl._identity.node_id]) == 1

        total_received = sum(len(msgs) for msgs in received_by_node.values())
        assert total_received == 2
    finally:
        for ctrl in controllers:
            await ctrl.stop()
