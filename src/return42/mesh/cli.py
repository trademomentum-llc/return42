"""CLI for mesh operations."""

from __future__ import annotations

import asyncio
import os

import typer

from return42.observability.evidence import EvidenceLogger
from return42.observability.telemetry import EventLevel, TelemetryEvent

from .controller import SmeshController
from .identity import NodeIdentity
from .message import MeshMessage, MessageTopic
from .transport import InMemoryTransport
from .transport_mqtt import MqttTransport

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
) -> None:
    """Run a single mesh node."""

    async def run() -> None:
        identity = NodeIdentity.generate(node_id)
        if transport == "memory":
            tx = InMemoryTransport()
        elif transport == "mqtt":
            tx = MqttTransport(node_id=node_id)
        else:
            raise typer.BadParameter(f"Unknown transport: {transport}")

        evidence = EvidenceLogger(log_dir=log_dir)
        controller = SmeshController(identity, tx, heartbeat_interval=heartbeat)

        async def log_handler(msg: MeshMessage) -> None:
            evidence.write(_mesh_message_to_telemetry(msg))

        for topic in MessageTopic:
            controller.on_message(topic, log_handler)
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
