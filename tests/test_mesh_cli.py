import asyncio
import subprocess
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from return42.mesh.cli import _make_evidence_handler, _mesh_message_to_telemetry, app
from return42.mesh.identity import NodeIdentity
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
    result = runner.invoke(observability_app, ["mesh-node", "--help"], env={"COLUMNS": "200"})
    assert result.exit_code == 0
    assert "--node-id" in result.output
    assert "--transport" in result.output
    assert "--heartbeat" in result.output
    assert "--trust-on-first-use" in result.output
    assert "--trusted-peers" in result.output


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


def test_mesh_node_help_lists_trust_options():
    result = runner.invoke(app, ["mesh-node", "--help"], env={"COLUMNS": "200"})
    assert result.exit_code == 0
    assert "--trust-on-first-use" in result.output
    assert "--no-trust-on-first-use" in result.output
    assert "--trusted-peers" in result.output


def _run_mesh_node(args):
    """Invoke mesh-node with a controller that exits the sleep loop immediately."""
    identity = NodeIdentity.generate("som-a")
    controller = MagicMock()
    controller.peers = set()
    controller.start = AsyncMock()
    controller.stop = AsyncMock()

    with patch("return42.mesh.cli.NodeIdentity.from_env", return_value=identity), \
         patch("return42.mesh.cli.SmeshController", return_value=controller) as mock_controller, \
         patch("return42.mesh.cli.asyncio.sleep", side_effect=asyncio.CancelledError):
        result = runner.invoke(app, args)

    return result, mock_controller, controller


def test_mesh_node_uses_trust_options():
    result, mock_controller, _ = _run_mesh_node([
        "--node-id",
        "som-a",
        "--trust-on-first-use",
        "--trusted-peers",
        "peer1:key1,peer2:key2",
    ])
    assert result.exit_code == 0
    trust_store = mock_controller.call_args.kwargs["trust_store"]
    assert trust_store.is_tofu is True
    assert trust_store.is_trusted("peer1")
    assert trust_store.is_trusted("peer2")
    assert trust_store.get_key("peer1") == "key1"
    assert trust_store.get_key("peer2") == "key2"


def test_mesh_node_trust_options_override_env(monkeypatch):
    monkeypatch.setenv("TRUST_ON_FIRST_USE", "true")
    monkeypatch.setenv("TRUSTED_PEERS", "env-peer:env-key")

    result, mock_controller, _ = _run_mesh_node([
        "--node-id",
        "som-a",
        "--no-trust-on-first-use",
        "--trusted-peers",
        "cli-peer:cli-key",
    ])
    assert result.exit_code == 0
    trust_store = mock_controller.call_args.kwargs["trust_store"]
    assert trust_store.is_tofu is False
    assert trust_store.is_trusted("cli-peer")
    assert trust_store.get_key("cli-peer") == "cli-key"
    assert not trust_store.is_trusted("env-peer")


def test_mesh_node_falls_back_to_env_trust_settings(monkeypatch):
    monkeypatch.setenv("TRUST_ON_FIRST_USE", "true")
    monkeypatch.setenv("TRUSTED_PEERS", "env-peer:env-key")

    result, mock_controller, _ = _run_mesh_node([
        "--node-id",
        "som-a",
    ])
    assert result.exit_code == 0
    trust_store = mock_controller.call_args.kwargs["trust_store"]
    assert trust_store.is_tofu is True
    assert trust_store.is_trusted("env-peer")
    assert trust_store.get_key("env-peer") == "env-key"


def test_sandbox_help_lists_trust_options():
    result = subprocess.run(
        [sys.executable, "scripts/run_mesh_sandbox.py", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "--trust-on-first-use" in result.stdout
    assert "--no-trust-on-first-use" in result.stdout
    assert "--trusted-peers" in result.stdout
