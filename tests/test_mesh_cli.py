from typer.testing import CliRunner

from return42.mesh.cli import _mesh_message_to_telemetry, app
from return42.mesh.message import MeshMessage, MessageTopic
from return42.observability.cli import app as observability_app

runner = CliRunner()


def test_mesh_node_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "mesh-node" in result.output


def test_observability_cli_mesh_node_help():
    """The top-level observability CLI must expose the mesh-node command."""
    result = runner.invoke(observability_app, ["mesh-node", "--help"])
    assert result.exit_code == 0
    assert "--node-id" in result.output
    assert "--transport" in result.output
    assert "--heartbeat" in result.output


def test_mesh_message_to_telemetry_preserves_signature():
    """Evidence conversion should include the message signature in the payload."""
    msg = MeshMessage(
        source="node-a",
        destination="node-b",
        topic=MessageTopic.COMMAND,
        payload={"action": "ping"},
        signature="sig-12345",
    )
    event = _mesh_message_to_telemetry(msg)
    assert event.payload["signature"] == "sig-12345"
    assert event.payload["topic"] == "command"
    assert event.payload["destination"] == "node-b"
    assert event.payload["data"] == {"action": "ping"}
    assert event.name == "mesh.message.command"
    assert event.source == "node-a"
