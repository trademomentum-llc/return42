# Design Specifications (v1)

## Architecture
Dual-plane architecture:
- **Local Mesh Plane:** XIAO SOM discovery, transport, local command exchange.
- **Trust Plane:** GSS-based identity/bootstrap that gates high-risk operations.
- **Gateway Plane:** NUC bridge and policy control for WAN/SIP integration.
- **SIP Plane:** Conditional route for external signaling when WAN and carrier policy allow.

## Topology
1. SOM nodes join a local mesh.
2. Nodes exchange discovery and heartbeat.
3. Nodes run GSS trust bootstrap and derive trust level.
4. Low-risk traffic follows local-only routes.
5. Gateway requests invoke external routing only when trust is sufficient and policy permits.

## Trust flow
1. Discovery
2. GSS context negotiation
3. Capability advertisement based on trust level
4. Command/control exchange
5. Optional SIP bridge
6. Fallback to local-only on trust failure

## Security
- Mutual identity verification via GSS trust context.
- Integrity/signature and replay protection on control commands.
- Local-only mode for low trust/failure states.
- Gateway access controlled by policy and trust-level gates.

## Reliability
- Heartbeats and watchdogs on each SOM.
- Exponential backoff for retries and queueing.
- Gateway health checks (`mesh_up`, `gateway_reachability`, `sip_register`, `queue_depth`).
- Telemetry-driven auto-healing for route recovery.

## Workstreams
- Stream A: local-first baseline and failover behaviors.
- Stream B: SIP gateway and identity integration (parallel path).
- Convergence: API contract parity and consistent policy checks.

## Implementation status (2026-07-08)
- Trust plane reference module landed: `gss-trust-plane/` (mock GSS / HMAC).
- Policy: SIP and elevated control require `trust_level >= medium`.
- Local-only fallback verified in HIL evidence.
- Cross-link: NASN mesh design under `NeuroDiOS/docs/superpowers/specs/`.
