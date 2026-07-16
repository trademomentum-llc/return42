"""CLI for mesh operations."""

from __future__ import annotations

import asyncio
import os

import typer

from return42.observability.evidence import EvidenceLogger
from return42.observability.telemetry import EventLevel, TelemetryEvent

from .controller import MessageHandler, SmeshController
from .identity import NodeIdentity
from .message import MeshMessage, MessageTopic
from .transport import InMemoryTransport
from .transport_mqtt import MqttTransport
from .trust import TrustStore

app = typer.Typer(help="Return42 mesh commands")


def _mesh_message_to_telemetry(msg: MeshMessage) -> TelemetryEvent:
    """Convert a mesh message into a telemetry event for evidence logging."""
    return TelemetryEvent(
        name=f"mesh.message.{msg.topic.value}",
        source=msg.source,
        level=EventLevel.INFO,
        payload={
            "topic": msg.topic.value,
            "destination": msg.destination,
            "msg_id": msg.msg_id,
            "timestamp": msg.timestamp,
            "data": msg.payload,
            "signature": msg.signature,
        },
    )


def _make_evidence_handler(evidence: EvidenceLogger) -> MessageHandler:
    """Return an async handler that offloads evidence writes to a worker thread."""

    async def handler(msg: MeshMessage) -> None:
        await asyncio.to_thread(evidence.write, _mesh_message_to_telemetry(msg))

    return handler


def _parse_trusted_peers(raw: str) -> dict[str, str]:
    """Parse a comma-separated list of ``node_id:verify_key`` entries."""
    peers: dict[str, str] = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        peer_id, key = entry.split(":", 1)
        peers[peer_id.strip()] = key.strip()
    return peers


@app.command("mesh-node")
def mesh_node(
    node_id: str = typer.Option(..., "--node-id", help="Unique node identifier"),
    transport: str = typer.Option("memory", "--transport", help="memory or mqtt"),
    heartbeat: float = typer.Option(1.0, "--heartbeat", help="Heartbeat interval in seconds"),
    log_dir: str = typer.Option(
        os.getenv("EVIDENCE_LOG_DIR", "evidence"),
        "--log-dir",
        envvar="EVIDENCE_LOG_DIR",
    ),
    trust_on_first_use: bool | None = typer.Option(
        None,
        "--trust-on-first-use/--no-trust-on-first-use",
        help="Trust peers on first discovery (overrides TRUST_ON_FIRST_USE)",
    ),
    trusted_peers: str | None = typer.Option(
        None,
        "--trusted-peers",
        help="Comma-separated node_id:verify_key peers (overrides TRUSTED_PEERS)",
    ),
) -> None:
    """Run a single mesh node."""

    async def run() -> None:
        identity = NodeIdentity.from_env(node_id=node_id)
        if transport == "memory":
            tx = InMemoryTransport()
        elif transport == "mqtt":
            tx = MqttTransport(node_id=node_id)
        else:
            raise typer.BadParameter(f"Unknown transport: {transport}")

        trust_store = TrustStore.from_env()
        if trust_on_first_use is not None:
            # Rebuild the store with the explicit CLI TOFU flag while
            # preserving any pre-enrolled peers loaded from the environment.
            trust_store = TrustStore(
                tofu=trust_on_first_use,
                trusted_peers=trust_store.trusted_peers,
            )
        if trusted_peers is not None:
            trust_store = TrustStore(
                tofu=trust_store.is_tofu,
                trusted_peers=_parse_trusted_peers(trusted_peers),
            )

        evidence = EvidenceLogger(log_dir=log_dir)
        controller = SmeshController(
            identity,
            tx,
            heartbeat_interval=heartbeat,
            trust_store=trust_store,
        )

        for topic in MessageTopic:
            controller.on_message(topic, _make_evidence_handler(evidence))
        await controller.start()
        typer.echo(f"Node {node_id} running with {transport} transport. Peers: {controller.peers}")
        try:
            while True:
                await asyncio.sleep(5)
                typer.echo(f"Peers: {controller.peers}")
        except asyncio.CancelledError:
            pass
        finally:
            await controller.stop()

    asyncio.run(run())
