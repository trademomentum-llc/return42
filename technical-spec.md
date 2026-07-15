# Technical Specifications (v1)

## Recommended stack
- Local control: MQTT/CoAP over Wi-Fi/mesh with mTLS for transport-level auth.
- Trust: GSS (Apple GSS.framework on Apple clients; GSSAPI/Kerberos on Linux).
- Gateway: NUC running containerized services.
- SIP: Asterisk or FreeSWITCH with bridge policy and auth controls.
- Observability: Prometheus/Grafana or lightweight equivalent.

## Interfaces
- SOM <-> SOM: local mesh transport.
- SOM <-> NUC: authenticated API socket/gRPC.
- NUC <-> Phones: LAN Wi-Fi APIs and optional dashboard.
- NUC <-> WAN: SIP signaling and optional backends.

## API contract
- `POST /mesh/join`
- `POST /mesh/message`
- `GET /mesh/health`
- `POST /trust/session` (body: `gss_token`, `gss_context_id`, `gss_peer_id`, `gss_expiry_unix`, `trust_level`)
- `POST /sip/session` (subject to trust level)
- `POST /gateway/sync`

## Service components
1. `smesh-controller`
2. `identity-service` (trust plane) — implemented in `gss-trust-plane/src/gss_trust_plane/identity.py`
3. `gss-client` (SOM) — mock client via join/bootstrap; real GSS client backlog
4. `gateway-api` — implemented in `gss-trust-plane/src/gss_trust_plane/gateway.py`
5. `sip-gateway` — policy-gated via `/sip/session` (Asterisk/FreeSWITCH bind residual)
6. `telemetry-stack` — in-process TelemetryBus + JSONL evidence

## Implementation reference
- Module path: `gss-trust-plane/`
- HIL: `python3 gss-trust-plane/scripts/run_hil.py`
- Demo: `python3 gss-trust-plane/scripts/demo_uplift.py`

## Data fields
- `gss_token`
- `gss_context_id`
- `gss_peer_id`
- `gss_expiry_unix`
- `trust_level`

## Test matrix
1. Local-only messaging with 3 SOM nodes.
2. WAN off with queue/replay on restore.
3. GSS success/failure/replay/expiry scenarios.
4. SIP session routing from Pixel 9 when allowed.
5. Local-only policy on Pixel 10.
6. Gateway restart during active operations and reconciliation.
