from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from return42.mesh.cli import _make_evidence_handler, _mesh_message_to_telemetry, app
from return42.mesh.message import MeshMessage, MessageTopic
from return42.observability.cli import app as observability_app
from return42.observability.evidence import EvidenceLogger

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


@pytest.mark.asyncio
async def test_evidence_handler_offloads_write_to_thread(tmp_path):
    """The async evidence handler must not perform synchronous file I/O."""
    evidence = EvidenceLogger(log_dir=str(tmp_path))
    handler = _make_evidence_handler(evidence)
    msg = MeshMessage(
        source="node-a",
        destination="node-b",
        topic=MessageTopic.COMMAND,
        payload={"action": "ping"},
    )

    with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
        await handler(msg)

    mock_to_thread.assert_awaited_once()
    # Ensure the callable passed to to_thread is the synchronous evidence.write.
    call_args = mock_to_thread.call_args
    assert call_args[0][0] == evidence.write
