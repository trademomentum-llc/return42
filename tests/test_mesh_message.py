from return42.mesh.identity import NodeIdentity
from return42.mesh.message import MeshMessage, MessageTopic


def test_mesh_message_defaults():
    msg = MeshMessage(source="som-01", destination="som-02", topic=MessageTopic.HEARTBEAT, payload={"rssi": -42})
    assert msg.source == "som-01"
    assert msg.topic == "heartbeat"
    assert msg.payload["rssi"] == -42
    assert msg.msg_id is not None


def test_message_signature_round_trip():
    node = NodeIdentity.generate("som-a")
    msg = MeshMessage(source="som-a", topic=MessageTopic.COMMAND, payload={"action": "ping"})
    signed = msg.sign(node)
    assert signed.signature is not None
    assert signed.verify(node) is True


def test_message_signature_detects_tampering():
    node = NodeIdentity.generate("som-a")
    msg = MeshMessage(source="som-a", topic=MessageTopic.COMMAND, payload={"action": "ping"})
    signed = msg.sign(node)
    tampered = signed.model_copy(update={"payload": {"action": "pwn"}})
    assert tampered.verify(node) is False
