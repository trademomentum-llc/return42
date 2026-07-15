"""Run a 3-node local mesh sandbox."""

import asyncio

from return42.mesh.controller import SmeshController
from return42.mesh.identity import NodeIdentity
from return42.mesh.message import MessageTopic
from return42.mesh.transport import InMemoryTransport


async def main() -> None:
    bus = InMemoryTransport()
    nodes = [NodeIdentity.generate(f"som-{i}") for i in range(3)]
    controllers = [SmeshController(node, bus, heartbeat_interval=1.0) for node in nodes]

    async def handler(msg):
        print(f"[{msg.destination or 'broadcast'}] {msg.source}: {msg.payload}")

    for ctrl in controllers:
        ctrl.on_message(MessageTopic.COMMAND, handler)
        await ctrl.start()

    print("Sandbox running. Press Ctrl+C to stop.")
    for ctrl in controllers:
        print(f"{ctrl.node_id} peers: {ctrl.peers}")
    try:
        while True:
            await asyncio.sleep(5)
            for ctrl in controllers:
                print(f"{ctrl.node_id} peers: {ctrl.peers}")
    except asyncio.CancelledError:
        pass
    finally:
        for ctrl in controllers:
            await ctrl.stop()


if __name__ == "__main__":
    asyncio.run(main())
