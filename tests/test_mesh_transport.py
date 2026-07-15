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
