from return42.mesh.message import MeshMessage, MessageTopic


def test_mesh_message_defaults():
    msg = MeshMessage(source="som-01", destination="som-02", topic=MessageTopic.HEARTBEAT, payload={"rssi": -42})
    assert msg.source == "som-01"
    assert msg.topic == "heartbeat"
    assert msg.payload["rssi"] == -42
    assert msg.msg_id is not None
