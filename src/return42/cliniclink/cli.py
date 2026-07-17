from __future__ import annotations

import asyncio
import os

import typer

from return42.mesh.identity import NodeIdentity
from return42.mesh.transport_mqtt import MqttTransport
from return42.mesh.transport import InMemoryTransport
from return42.mesh.trust import TrustStore

from .gateway import ClinicGatewayController

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
) -> None:
    async def run() -> None:
        identity = NodeIdentity.from_env(node_id)
        if transport == "memory":
            tx = InMemoryTransport()
        elif transport == "mqtt":
            tx = MqttTransport(node_id=node_id)
        else:
            raise typer.BadParameter(f"Unknown transport: {transport}")

        controller = ClinicGatewayController(
            identity=identity,
            transport=tx,
            db_path=db_path,
            queue_db_path=queue_db_path,
            trust_store=TrustStore.from_env(),
        )
        await controller.start()
        typer.echo(f"ClinicLink gateway {node_id} running.")
        try:
            while True:
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            pass
        finally:
            await controller.stop()

    asyncio.run(run())
