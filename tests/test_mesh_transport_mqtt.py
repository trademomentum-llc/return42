import asyncio

import aiomqtt
import pytest

from return42.mesh.message import MeshMessage, MessageTopic
from return42.mesh.transport_mqtt import MqttTransport
from tests.conftest import _wait_for


@pytest.mark.asyncio
async def test_mqtt_transport_serialization():
    transport = MqttTransport(host="127.0.0.1", port=1883, node_id="test")
    msg = MeshMessage(source="a", topic=MessageTopic.HEARTBEAT, payload={"seq": 1})
    data = transport._encode(msg)
    decoded = transport._decode(data)
    assert decoded.source == "a"
    assert decoded.topic == MessageTopic.HEARTBEAT
    assert decoded.payload == {"seq": 1}


@pytest.mark.asyncio
async def test_mqtt_transport_receive_dispatches_to_handlers(monkeypatch):
    received = []

    async def heartbeat_handler(msg: MeshMessage) -> None:
        received.append(("heartbeat", msg))

    async def command_handler(msg: MeshMessage) -> None:
        received.append(("command", msg))

    heartbeat_msg = MeshMessage(
        source="node-a", topic=MessageTopic.HEARTBEAT, payload={"seq": 1}
    )
    command_msg = MeshMessage(
        source="node-b", topic=MessageTopic.COMMAND, payload={"action": "ping"}
    )
    invalid_payload = b"not-valid-json"

    async def fake_messages():
        yield aiomqtt.Message(
            "heartbeat", heartbeat_msg.model_dump_json().encode("utf-8"), 0, False, 1, None
        )
        yield aiomqtt.Message(
            "command", command_msg.model_dump_json().encode("utf-8"), 0, False, 2, None
        )
        # Invalid payload should be skipped without crashing the loop.
        yield aiomqtt.Message("heartbeat", invalid_payload, 0, False, 3, None)
        # Keep the iterator alive until the receive task is cancelled.
        await asyncio.Event().wait()

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.subscriptions: list[str] = []
            self.published: list[tuple[str, bytes]] = []
            self.messages = fake_messages()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def subscribe(self, topic):
            self.subscriptions.append(topic)

        async def publish(self, topic, payload):
            self.published.append((topic, payload))

    monkeypatch.setattr("return42.mesh.transport_mqtt.Client", FakeClient)

    transport = MqttTransport(host="127.0.0.1", port=1883, node_id="test")

    # Subscribe before start; the broker subscription should be replayed once connected.
    await transport.subscribe("heartbeat", heartbeat_handler)
    await transport.start()
    # Subscribe after start.
    await transport.subscribe("command", command_handler)

    # Wait for the two valid messages to be dispatched.
    await _wait_for(lambda: len(received) == 2)

    fake_client = transport._client
    await transport.stop()

    assert ("heartbeat", heartbeat_msg.source) in [(kind, m.source) for kind, m in received]
    assert ("command", command_msg.source) in [(kind, m.source) for kind, m in received]
    assert any(m.topic == MessageTopic.COMMAND for _, m in received)
    assert "heartbeat" in fake_client.subscriptions
    assert "command" in fake_client.subscriptions


@pytest.mark.asyncio
async def test_mqtt_transport_start_failure_leaves_client_none(monkeypatch):
    class FailingClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            raise RuntimeError("connection refused")

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr("return42.mesh.transport_mqtt.Client", FailingClient)

    transport = MqttTransport(host="127.0.0.1", port=1883, node_id="test")
    with pytest.raises(RuntimeError, match="connection refused"):
        await transport.start()

    assert transport._client is None
    assert transport._receive_task is None
