import asyncio

import pytest

from return42.mesh.controller import SmeshController
from return42.mesh.identity import NodeIdentity
from return42.mesh.message import MessageTopic
from return42.mesh.transport import InMemoryTransport


async def _wait_for(predicate, timeout: float = 1.0, interval: float = 0.01):
    deadline = asyncio.get_event_loop().time() + timeout
    while not predicate():
        if asyncio.get_event_loop().time() >= deadline:
            raise TimeoutError("Predicate was not satisfied in time")
        await asyncio.sleep(interval)


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
            ctrl.on_message(MessageTopic.COMMAND, make_handler(ctrl.node_id))
            await ctrl.start()

        # Wait for all nodes to discover each other (deterministic).
        await _wait_for(lambda: all(len(c.peers) == 2 for c in controllers))

        sender = controllers[0]
        await sender.send(MessageTopic.COMMAND, {"action": "ping"})

        # Wait for the two non-sender nodes to receive the command.
        await _wait_for(
            lambda: sum(len(msgs) for msgs in received_by_node.values()) == 2
        )

        # Sender should not receive its own command; the other two should.
        assert len(received_by_node[sender.node_id]) == 0
        for ctrl in controllers[1:]:
            assert len(received_by_node[ctrl.node_id]) == 1

        total_received = sum(len(msgs) for msgs in received_by_node.values())
        assert total_received == 2
    finally:
        for ctrl in controllers:
            await ctrl.stop()
