from __future__ import annotations

import asyncio
import os
import signal
import sys

import typer
import uvicorn

from return42.mesh.identity import NodeIdentity
from return42.mesh.transport_mqtt import MqttTransport
from return42.mesh.transport import InMemoryTransport
from return42.mesh.trust import TrustStore
from return42.observability.evidence import EvidenceLogger
from return42.observability.telemetry import TelemetryBus

from .api import create_app
from .gateway import ClinicGatewayController
from .queue import SyncQueue
from .store import HandoffStore

app = typer.Typer(help="ClinicLink ambulance-to-clinic handoff")


@app.callback()
def main() -> None:
    """ClinicLink ambulance-to-clinic handoff."""


@app.command("gateway")
def gateway(
    node_id: str = typer.Option(..., "--node-id", help="Clinic node identifier"),
    transport: str = typer.Option("memory", "--transport", help="memory or mqtt"),
    db_path: str = typer.Option("cliniclink.db", "--db-path"),
    queue_db_path: str = typer.Option("cliniclink_queue.db", "--queue-db-path"),
    api_host: str = typer.Option("0.0.0.0", "--api-host", help="HTTP API host"),
    api_port: int = typer.Option(8000, "--api-port", help="HTTP API port"),
) -> None:
    async def run() -> None:
        identity = NodeIdentity.from_env(node_id)
        if transport == "memory":
            tx = InMemoryTransport()
        elif transport == "mqtt":
            tx = MqttTransport(node_id=node_id)
        else:
            raise typer.BadParameter(f"Unknown transport: {transport}")

        trust_store = TrustStore.from_env()
        store = HandoffStore(db_path)
        queue = SyncQueue(queue_db_path)
        telemetry_bus = TelemetryBus()
        evidence = EvidenceLogger()

        controller = ClinicGatewayController(
            identity=identity,
            transport=tx,
            db_path=db_path,
            queue_db_path=queue_db_path,
            trust_store=trust_store,
            store=store,
            queue=queue,
            telemetry_bus=telemetry_bus,
        )

        for event_name in (
            "mesh.message.sent",
            "mesh.message.received",
            "mesh.message.signature_invalid",
            "mesh.peer.trusted",
            "mesh.peer.untrusted",
            "mesh.command.rejected",
            "cliniclink.handoff.received",
            "cliniclink.handoff.rejected",
            "cliniclink.handoff.acknowledged",
        ):
            telemetry_bus.subscribe(event_name, evidence.write)

        app = create_app(
            db_path=db_path,
            queue_db_path=queue_db_path,
            trust_store=trust_store,
            store=store,
            queue=queue,
            telemetry_bus=telemetry_bus,
        )
        config = uvicorn.Config(
            app,
            host=api_host,
            port=api_port,
            log_level="info",
            handle_signals=False,
        )
        server = uvicorn.Server(config)

        await controller.start()
        typer.echo(
            f"ClinicLink gateway {node_id} running on mesh ({transport}) "
            f"and HTTP API at http://{api_host}:{api_port}"
        )

        server_task = asyncio.create_task(server.serve())
        stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()

        def on_signal() -> None:
            typer.echo("Shutdown signal received, stopping gateway...")
            stop_event.set()

        # Unix only: asyncio signal handlers are not supported on Windows.
        if sys.platform != "win32":
            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.add_signal_handler(sig, on_signal)
                except (NotImplementedError, ValueError):
                    pass

        try:
            await stop_event.wait()
        finally:
            server.should_exit = True
            await server_task
            await controller.stop()
            if sys.platform != "win32":
                for sig in (signal.SIGINT, signal.SIGTERM):
                    try:
                        loop.remove_signal_handler(sig)
                    except (NotImplementedError, ValueError):
                        pass

    asyncio.run(run())
