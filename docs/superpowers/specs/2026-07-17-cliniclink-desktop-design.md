# ClinicLink Desktop Design Spec

> **Status:** Draft awaiting review  
> **Date:** 2026-07-17  
> **Topic:** Cross-platform desktop GUI for ClinicLink ambulance-to-clinic handoff  

## 1. Goal

Build a cross-platform desktop application that lets clinic staff receive and acknowledge patient handoffs, and lets ambulance crews create and send handoffs, over the Return42 mesh when cellular connectivity is unavailable. The first version focuses on the core bidirectional handoff workflow; a multi-clinic coordination dashboard is deferred to Phase 2.

## 2. Context

ClinicLink v1.0.0 provides:

- `return42.cliniclink` Python package with models, store, policy, queue, API, dashboard, ambulance client, and gateway controller.
- `r42-cliniclink` CLI for running the clinic gateway and ambulance sync client.
- A static web dashboard served by the gateway.
- Signed mesh messaging via `SmeshController` and `TrustStore`.

The desktop app adds a native graphical interface on top of these existing primitives.

## 3. Architecture

```
┌─────────────────────────────────────────────┐
│  ClinicLink Desktop (Tauri + React/TS)      │
│  ┌──────────────┐      ┌─────────────────┐  │
│  │  React UI    │◄────►│  Tauri Commands │  │
│  │              │      │  + Events       │  │
│  └──────────────┘      └────────┬────────┘  │
│                                 │           │
│  Tauri Rust shell (window, tray, keychain)  │
└─────────────────────────────────┬───────────┘
                                  │ HTTP + WebSocket
┌─────────────────────────────────┴───────────┐
│  Python Sidecar                               │
│  return42.cliniclink.desktop_sidecar          │
│  - Local HTTP API (127.0.0.1)                 │
│  - WebSocket event stream                     │
│  - Clinic mode: proxies local gateway         │
│  - Ambulance mode: runs AmbulanceSyncClient   │
└─────────────────────────────────────────────┘
```

The frontend never holds signing keys or talks directly to the mesh. The sidecar manages all cryptography, trust, and PHI. Only UI-safe data crosses the IPC boundary.

## 4. Modes and Workflows

### 4.1 Mode Picker

On first launch the user selects a mode. The choice is persisted in Tauri-managed settings (not browser storage). Mode switching restarts the sidecar's internal services.

### 4.2 Clinic Mode

- Connects to the local `r42-cliniclink gateway`.
- Shows a live list of incoming handoffs with status, ETA, vital signs, medications, and chief complaint.
- One-click acknowledge with optional notes.
- Audible and visual notification for new pending handoffs.
- Persistent "connection status" indicator (mesh connected / degraded / offline).

### 4.3 Ambulance Mode

- Discovers nearby clinic gateways over the Return42 mesh.
- Form to create a new handoff: patient ID, chief complaint, vital signs, medications, ETA.
- Submit to selected clinic.
- Show delivery status: queued / sent / acknowledged.
- If no clinic is in mesh range, queue locally and auto-send when a trusted clinic appears.

### 4.4 Phase 2 (Deferred)

- Real-time map/ETA view.
- Multi-clinic dispatch oversight.
- Supervisor dashboard.

## 5. Sidecar API

The sidecar binds to `127.0.0.1` on a dynamically chosen port (starting at `2842`). Tauri spawns the sidecar process on app launch and terminates it on app exit. The sidecar prints its chosen port to stdout in a well-known line (e.g., `SIDECAR_PORT=2842`) that Tauri parses before opening the WebSocket.

### 5.1 HTTP Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Sidecar health |
| GET | `/mode` | Current mode: `clinic` or `ambulance` |
| POST | `/mode` | Switch mode |
| GET | `/identity` | Public node ID and verify key |
| POST | `/trust` | Pre-enroll a peer verify key |

#### Clinic Mode

| Method | Path | Description |
|--------|------|-------------|
| GET | `/handoffs` | List handoffs, optional `status` filter |
| GET | `/handoffs/{id}` | Get one handoff |
| POST | `/handoffs/{id}/ack` | Acknowledge a handoff |

#### Ambulance Mode

| Method | Path | Description |
|--------|------|-------------|
| GET | `/clinics` | List discovered clinic nodes |
| POST | `/handoffs` | Create and submit a handoff |
| GET | `/outbox` | List queued/outgoing handoffs and statuses |

### 5.2 WebSocket Events

`WS /events` emits JSON messages:

```json
{
  "type": "handoff.received",
  "timestamp": "2026-07-17T12:00:00Z",
  "payload": { "handoff_id": "ho-123", "patient_id": "p-456", ... }
}
```

Event types:

- `handoff.received`
- `handoff.acknowledged`
- `handoff.queued`
- `handoff.sent`
- `clinic.discovered`
- `clinic.lost`
- `mesh.peer.joined`
- `mesh.peer.lost`
- `connection.degraded`
- `connection.restored`

Commands may also be sent over the WebSocket; HTTP POST remains a fallback.

## 6. Real-Time Event Layer

- Tauri Rust holds one persistent WebSocket connection to the sidecar.
- Sidecar events are forwarded to the frontend via Tauri `emit`.
- Frontend subscribes with `listen('cliniclink:event', callback)`.
- If the WebSocket drops, the frontend falls back to HTTP POST for commands and periodic HTTP GET for state until the socket reconnects automatically.

## 7. Security and PHI Protection

- **Signing keys** are stored only in OS secure storage (Keychain / DPAPI / Secret Service) and injected into the sidecar on startup. The frontend never sees `NODE_SIGNING_KEY`.
- **Tokens** (`CLINIC_TOKEN`, `CLINICLINK_ADMIN_TOKEN`) are stored the same way.
- **PHI** is rendered in the frontend but kept in memory only; no browser localStorage/sessionStorage for patient data.
- **Network binding:** sidecar listeners bind to `127.0.0.1` only.
- **Trust:** mesh signatures are verified by the sidecar before any handoff is accepted or displayed.

## 8. Tech Stack

| Layer | Technology |
|-------|------------|
| Desktop shell | Tauri v2 |
| Frontend | React + TypeScript |
| State / server sync | TanStack Query + Zustand |
| Sidecar | Existing `return42` Python package |
| Sidecar HTTP/WebSocket | FastAPI + `fastapi.websockets` |
| IPC | Tauri commands + Tauri events |
| Secure storage | Tauri Stronghold plugin (or OS keychain plugin) for secrets; runtime env vars for the sidecar |
| Build | `cargo tauri`, `npm`, PyInstaller |

## 9. Packaging and Deployment

- The PyInstaller-built `r42-cliniclink` and `r42-observe` binaries serve as the sidecar.
- Tauri bundles the frontend and Rust shell into a native executable per platform.
- Platform installers are updated:
  - macOS `.pkg` installs CLI binaries + `ClinicLink Desktop.app`.
  - Windows `.exe` installs CLI binaries + `ClinicLink Desktop.exe`.
  - Linux `.deb` installs CLI binaries + `cliniclink-desktop`.
- The GitHub Actions `release-installers.yml` workflow gains a `build-tauri` job.

## 10. Testing Strategy

### 10.1 Flow Tests

- Ambulance creates handoff → mesh delivers → clinic receives → clinic acknowledges → ambulance sees ack.
- Handoff retry when clinic offline, then auto-delivers on reconnect.
- Duplicate handoff idempotency across the full pipeline.

### 10.2 Redundancy Tests

- Multiple ambulances hand off to one clinic concurrently.
- Clinic gateway restart replays queued handoffs correctly.
- WebSocket down + HTTP POST fallback still acknowledges a handoff.

### 10.3 UI Tests

- New pending handoff triggers visible + audible alert within 1 second.
- Acknowledge button updates state immediately and prevents double-submit.
- Mode switch restarts services cleanly.

### 10.4 Bottleneck Tests

- 100 simultaneous handoffs into one clinic; UI stays responsive.
- 24-hour soak test with heartbeats and random disconnects.

### 10.5 Signal / Connectivity Tests

- WebSocket reconnects after sidecar restart.
- Mesh peer discovery and loss events reach the UI.
- Untrusted nodes are rejected.

### 10.6 Fallback Tests

- WebSocket failure → HTTP polling + POST fallback.
- Mesh unavailable → local queue + retry.
- Missing `NODE_SIGNING_KEY` blocks startup with a clear error dialog.

### 10.7 Security / PHI Tests

- Frontend cannot read signing keys from secure storage.
- PHI is not logged to Tauri/devtools console.
- Tokens survive app restart but are not readable by other apps.

## 11. Out of Scope (Phase 2)

- Multi-clinic dispatch map/ETA dashboard.
- Native mobile apps (iOS/Android).
- EHR integration (FHIR/HL7).
- SIP/voice bridge.
- Cloud sync or centralized server.

## 12. Success Criteria

- A clinic user can receive, view, and acknowledge a handoff sent by an ambulance user without touching the CLI.
- The app functions when the ambulance has no cellular/WAN connectivity but is within mesh range of the clinic.
- All listed tests pass before release.
