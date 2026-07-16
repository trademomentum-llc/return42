"""Run a 3-node local mesh sandbox."""

import argparse
import asyncio

from return42.mesh.controller import SmeshController
from return42.mesh.identity import NodeIdentity
from return42.mesh.message import MessageTopic
from return42.mesh.transport import InMemoryTransport
from return42.mesh.trust import TrustStore, parse_trusted_peers


def build_trust_store(tofu: bool | None, trusted_peers: str | None) -> TrustStore:
    """Resolve trust settings from CLI flags and environment."""
    store = TrustStore.from_env()
    if tofu is not None:
        store = TrustStore(
            tofu=tofu,
            trusted_peers=store.trusted_peers,
        )
    if trusted_peers is not None:
        store = TrustStore(
            tofu=store.is_tofu,
            trusted_peers=parse_trusted_peers(trusted_peers),
        )
    return store


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run a 3-node local mesh sandbox")
    parser.add_argument(
        "--trust-on-first-use",
        dest="tofu",
        action="store_true",
        default=None,
        help="Trust peers on first discovery",
    )
    parser.add_argument(
        "--no-trust-on-first-use",
        dest="tofu",
        action="store_false",
        default=None,
        help="Do not trust peers on first discovery",
    )
    parser.add_argument(
        "--trusted-peers",
        default=None,
        help="Comma-separated node_id:verify_key peers",
    )
    args = parser.parse_args()

    bus = InMemoryTransport()
    nodes = [NodeIdentity.generate(f"som-{i}") for i in range(3)]
    # Give each node its own TrustStore instance so the sandbox simulates
    # independent nodes that happen to share the same bootstrap parameters.
    controllers = [
        SmeshController(
            node,
            bus,
            heartbeat_interval=1.0,
            trust_store=build_trust_store(args.tofu, args.trusted_peers),
        )
        for node in nodes
    ]

    async def handler(msg):
        print(f"[{msg.destination or 'broadcast'}] {msg.source}: {msg.payload}", flush=True)

    for ctrl in controllers:
        ctrl.on_message(MessageTopic.COMMAND, handler)
        await ctrl.start()

    print("Sandbox running. Press Ctrl+C to stop.", flush=True)
    for ctrl in controllers:
        print(f"{ctrl.node_id} peers: {ctrl.peers}", flush=True)
    try:
        while True:
            await asyncio.sleep(5)
            for ctrl in controllers:
                print(f"{ctrl.node_id} peers: {ctrl.peers}", flush=True)
    except asyncio.CancelledError:
        pass
    except KeyboardInterrupt:
        pass
    finally:
        for ctrl in controllers:
            await ctrl.stop()


if __name__ == "__main__":
    asyncio.run(main())
