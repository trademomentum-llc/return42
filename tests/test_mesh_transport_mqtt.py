import pytest

from return42.mesh.message import MeshMessage, MessageTopic
from return42.mesh.transport_mqtt import MqttTransport


@pytest.mark.asyncio
async def test_mqtt_transport_serialization():
    transport = MqttTransport(host="127.0.0.1", port=1883, node_id="test")
    msg = MeshMessage(source="a", topic=MessageTopic.HEARTBEAT, payload={"seq": 1})
    data = transport._encode(msg)
    decoded = transport._decode(data)
    assert decoded.source == "a"
    assert decoded.topic == MessageTopic.HEARTBEAT
    assert decoded.payload == {"seq": 1}
