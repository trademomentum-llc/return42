# Requirements Document (v1)

## Objective
Build a resilient edge communication system using local-first networking plus a gateway bridge for WAN/SIP capabilities.

## Functional Requirements
1. XIAO SOM nodes must form a local mesh/network automatically and discover peers without manual pairing.
2. Device messages/commands/events shall route over local transport when WAN is unavailable.
3. A NUC gateway shall bridge local traffic to external services (SIP server, telemetry, backend services) when WAN is available.
4. Pixel 9 (unlocked, rooted) shall validate full SIP/IMS-style session signaling flows.
5. Pixel 10 (carrier-locked to Spectrum) shall validate local-only and app-layer workflows where cellular provisioning is unavailable.
6. Local operations must continue and queue data during gateway loss; queued events sync on recovery.
7. Communications must include identity, authentication, and integrity guarantees.
8. Telemetry must capture node status, link health, queue depth, and bridge translation outcomes.
9. Nodes must complete mutual trust bootstrap before elevated control-plane operations.
10. Nodes must sign control commands with trust-bound metadata.
11. If trust bootstrap fails, nodes stay in reduced local mode and cannot invoke gateway/SIP bridge actions.

## Non-Functional Requirements
1. Local control-plane messages should target median under 500ms under normal RF conditions.
2. Mesh path repair should complete within 5 seconds.
3. Gateway failover to local-only mode should occur in under 15 seconds.
4. Session logs must be local-persistent and rotatable.
5. Identity contexts should rotate on planned maintenance cycles.
6. GSS trust bootstrap for direct peers should complete by 2.0s median under normal local RF conditions.
7. Expired or stale trust contexts must be rejected and require re-authentication.

## Constraints
- SIP enables session signaling for IP networks; it does not create base physical connectivity.
- Pixel 10 is carrier-locked and cannot be treated as primary SIP endpoint for validation.
- Carrier policy and spectrum provisioning may restrict SIP/IMS behavior.

## Success Criteria
- Two SOM nodes exchange authenticated local messages without WAN.
- Same nodes optionally route sessions through SIP gateway when WAN is permitted.
- Pixel 9 runs signed SIP test cases.
- Pixel 10 validates local discovery, control UX, and diagnostics.
- WAN loss and recovery preserve queued state and resume sync.
- Failed trust bootstrap results in safe local-only fallback.

## Risks and Mitigations
1. Carrier policy limits IMS/SIP -> maintain local-first and parallel SIP path.
2. RF instability -> redundancy and retry/persistence tuning.
3. NUC single point of failure -> hardening and restart strategy.
4. GSS interoperability differences -> define strict token contract and conformance tests.
