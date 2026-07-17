# ClinicLink Desktop Technical Specification

> **Status:** Draft awaiting review  
> **Date:** 2026-07-17  
> **Topic:** Technical design for ClinicLink Desktop implementation  

## 1. Overview

This document details the technical implementation of ClinicLink Desktop: a Tauri-based cross-platform GUI with an embedded Python sidecar. It builds on the Requirements and Design Spec documents.

## 2. Repository Layout

```
cliniclink-desktop/               # New top-level directory
├── src-tauri/                    # Rust Tauri shell
│   ├── Cargo.toml
│   ├── tauri.conf.json
│   └── src/
│       ├── main.rs               # Entry point, sidecar spawn
│       ├── lib.rs                # Commands + event forwarding
│       └── sidecar.rs            # Sidecar process management
├── src/                          # React + TypeScript frontend
│   ├── main.tsx
│   ├── App.tsx
│   ├── components/
│   │   ├── ModeSelector.tsx
│   │   ├── ClinicView.tsx
│   │   ├── AmbulanceView.tsx
│   │   ├── HandoffCard.tsx
│   │   ├── HandoffForm.tsx
│   │   ├── ClinicList.tsx
│   │   └── ConnectionStatus.tsx
│   ├── hooks/
│   │   ├── useSidecar.ts
│   │   ├── useEvents.ts
│   │   └── useHandoffs.ts
│   └── api/
│       └── sidecar.ts
├── package.json
├── tsconfig.json
├── vite.config.ts
└── README.md

src/return42/cliniclink/          # Existing Python package additions
├── desktop_sidecar/
│   ├── __init__.py
│   ├── app.py                    # FastAPI app factory
│   ├── websocket.py              # WS event manager
│   ├── state.py                  # In-memory sidecar state
│   ├── clinic_service.py         # Clinic mode logic
│   └── ambulance_service.py      # Ambulance mode logic
```

## 3. Tauri Shell

### 3.1 Sidecar Spawning

On app launch, Tauri spawns the sidecar binary (`r42-cliniclink` with a new `sidecar` subcommand) and captures stdout.

- Tauri looks for the sidecar binary next to the app executable (bundled by the installer).
- The sidecar prints `SIDECAR_PORT=<port>` once it is listening.
- Tauri opens a WebSocket to `ws://127.0.0.1:<port>/events`.
- On app exit, Tauri sends SIGTERM and waits up to 5 seconds before SIGKILL.

### 3.2 Commands

Tauri exposes typed commands to the frontend:

```rust
#[tauri::command]
async fn sidecar_request(method: String, path: String, body: Option<String>) -> Result<String, String>;

#[tauri::command]
async fn get_mode() -> Result<String, String>;

#[tauri::command]
async fn set_mode(mode: String) -> Result<(), String>;

#[tauri::command]
async fn store_secret(key: String, value: String) -> Result<(), String>;

#[tauri::command]
async fn read_secret(key: String) -> Result<Option<String>, String>;
```

### 3.3 Event Forwarding

When the sidecar emits a WebSocket message, Tauri forwards it to the frontend:

```rust
app_handle.emit("cliniclink:event", payload)?;
```

## 4. Frontend

### 4.1 Framework

- React 18 with TypeScript.
- Vite for development and production builds.
- Tailwind CSS for styling.
- Radix UI or Headless UI for accessible primitives.

### 4.2 State Management

- **TanStack Query** for server state (handoffs, clinics, outbox).
- **Zustand** for client state (mode, connection status, selected clinic).
- **WebSocket events** invalidate TanStack Query caches immediately.

### 4.3 Event Handling

```typescript
import { listen } from '@tauri-apps/api/event';

listen('cliniclink:event', (event) => {
  const { type, payload } = event.payload;
  if (type === 'handoff.received') {
    queryClient.invalidateQueries({ queryKey: ['handoffs'] });
    playAlertSound();
  }
});
```

### 4.4 Views

- **ModeSelector:** simple two-card selection on first launch.
- **ClinicView:** split pane with handoff list and detail/acknowledge panel.
- **AmbulanceView:** clinic discovery list + handoff creation form + outbox status.
- **ConnectionStatus:** persistent bottom/top bar showing mesh and sidecar health.

## 5. Python Sidecar

### 5.1 Entry Point

Add a new CLI subcommand:

```bash
r42-cliniclink sidecar --port 2842
```

This starts the FastAPI + WebSocket server without blocking on gateway/ambulance logic until a mode is set.

### 5.2 FastAPI Application

```python
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# CORS restricted to Tauri WebView origin if needed; primarily loopback-only.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["tauri://localhost", "http://localhost"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 5.3 WebSocket Manager

- Maintains a set of connected clients (usually one: Tauri).
- Publishes events via `manager.broadcast(event)`.
- Accepts JSON commands over the WebSocket for bidirectional use.

### 5.4 Mode Services

#### Clinic Service

- Starts/stops a local `ClinicGatewayController` + FastAPI gateway.
- Subscribes to mesh events and forwards them as WebSocket events.
- Proxies HTTP requests to the local gateway.

#### Ambulance Service

- Starts/stops an `AmbulanceSyncClient`.
- Discovers clinics via mesh peer events.
- Queues outgoing handoffs in a local SQLite store when no clinic is reachable.
- Auto-dequeues when a trusted clinic is discovered.

### 5.5 Configuration

The sidecar reads:

- `NODE_ID`
- `NODE_SIGNING_KEY`
- `CLINIC_TOKEN`
- `CLINICLINK_ADMIN_TOKEN`
- `CLINICLINK_DB_PATH`
- `CLINICLINK_QUEUE_DB_PATH`

These are set by Tauri from secure storage before spawning the sidecar.

## 6. Data Contracts

### 6.1 Handoff Summary (frontend-safe)

```typescript
interface HandoffSummary {
  handoff_id: string;
  patient_id: string;
  ambulance_id: string;
  clinic_id: string;
  chief_complaint: string;
  eta_minutes: number | null;
  status: 'pending' | 'acknowledged' | 'rejected';
  created_at: string;
  acknowledged_at: string | null;
}
```

Note: `vital_signs` and `medications` are also passed to the frontend because they are needed for care; they are simply not persisted in browser storage.

### 6.2 Sidecar Event

```typescript
interface SidecarEvent {
  type: string;
  timestamp: string;
  payload: Record<string, unknown>;
}
```

### 6.3 Create Handoff Request

```typescript
interface CreateHandoffRequest {
  handoff_id: string;
  patient_id: string;
  clinic_id: string;
  chief_complaint: string;
  vital_signs: Record<string, unknown>;
  medications: string[];
  eta_minutes: number | null;
}
```

## 7. Communication Flows

### 7.1 Clinic Receive and Acknowledge

1. Ambulance sends handoff over mesh.
2. Clinic sidecar's `ClinicGatewayController` stores it and emits `handoff.received`.
3. Tauri forwards event to frontend.
4. Frontend displays alert and updates handoff list.
5. User clicks acknowledge.
6. Frontend calls Tauri command → HTTP POST `/handoffs/{id}/ack`.
7. Sidecar updates store and emits `handoff.acknowledged`.
8. Ambulance sidecar receives mesh ack and emits `handoff.acknowledged` to its frontend.

### 7.2 Ambulance Send

1. User selects target clinic from discovered list.
2. User fills form and submits.
3. Frontend calls Tauri command → HTTP POST `/handoffs`.
4. Sidecar creates `PatientHandoff` and attempts mesh send.
5. If clinic is reachable: emits `handoff.sent`.
6. If not reachable: stores in outbox queue and emits `handoff.queued`.
7. When clinic is discovered: auto-sends queued items and emits `handoff.sent`.

## 8. Security Details

### 8.1 Secret Storage

Use Tauri Stronghold plugin or OS keychain plugin:

```typescript
import { Stronghold } from 'tauri-plugin-stronghold-api';

const stronghold = new Stronghold('/path/to/vault.hold', 'password');
await stronghold.save_secret('NODE_SIGNING_KEY', signingKey);
```

### 8.2 Process Isolation

- The sidecar runs as a separate process with its own memory space.
- The frontend WebView cannot access the filesystem except through Tauri commands.
- The sidecar's HTTP/WebSocket listeners bind to `127.0.0.1` only.

### 8.3 PHI Handling

- PHI is rendered in DOM but not stored in `localStorage`, `sessionStorage`, or cookies.
- Tauri `csp` configuration restricts external resources.
- Console logging of handoff payloads is disabled in production builds.

## 9. Build and Packaging

### 9.1 Development

```bash
cd cliniclink-desktop
npm install
npm run tauri dev
```

### 9.2 Production Build

```bash
npm run tauri build
```

Outputs per platform:

- macOS: `src-tauri/target/release/bundle/macos/ClinicLink Desktop.app`
- Windows: `src-tauri/target/release/bundle/msi/ClinicLink Desktop_1.0.0_x64_en-US.msi`
- Linux: `src-tauri/target/release/bundle/deb/cliniclink-desktop_1.0.0_amd64.deb`

### 9.3 Installer Integration

Update existing platform installers to include the Tauri app:

- macOS `.pkg`: copy `.app` into `/Applications`.
- Windows `.exe`: copy `.exe` and supporting files into `Program Files\Return42`.
- Linux `.deb`: include Tauri `.deb` or bundle binaries manually.

## 10. Testing Plan

### 10.1 Sidecar Unit Tests

- `tests/test_desktop_sidecar_api.py` — HTTP endpoints.
- `tests/test_desktop_sidecar_websocket.py` — event broadcast and command handling.
- `tests/test_desktop_sidecar_mode_switch.py` — clinic/ambulance mode transitions.

### 10.2 Frontend Tests

- Vitest for component logic.
- React Testing Library for component rendering.
- Mock Tauri commands and events.

### 10.3 Integration Tests

- Start sidecar, connect WebSocket client, send handoff through `InMemoryTransport`, verify events.
- Test HTTP fallback when WebSocket is disconnected.

### 10.4 E2E Tests

- Tauri WebDriver or Playwright:
  - Clinic receive + acknowledge flow.
  - Ambulance create + send flow.
  - Mode switch.

### 10.5 Load and Resilience Tests

- 100 concurrent handoffs.
- Sidecar restart during active session.
- 24-hour heartbeat/soak test.

## 11. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Large bundle size from PyInstaller + Tauri | Strip Python stdlib, use UPX, ship platform-specific builds. |
| Tauri/WebView compatibility on older OS | Target supported Tauri platforms; test on CI. |
| WebSocket reconnection complexity | Implement exponential backoff with max jitter; fallback to HTTP. |
| PHI exposure via logs/devtools | Disable logging in release; audit all log sites. |
| Key loss if secure storage fails | Provide export/backup workflow for admins with encrypted backup. |

## 12. Dependencies

### 12.1 Frontend

- `react`, `react-dom`
- `typescript`, `vite`
- `@tauri-apps/api`
- `@tanstack/react-query`
- `zustand`
- `tailwindcss`
- `@radix-ui/react-*` or `@headlessui/react`

### 12.2 Rust / Tauri

- `tauri` v2
- `tauri-plugin-stronghold` or `tauri-plugin-os`
- `tokio-tungstenite` or `tauri` built-in HTTP client

### 12.3 Python

- Existing `return42` package
- `fastapi`, `uvicorn[standard]`, `websockets`

## 13. Migration and Compatibility

- The desktop app uses the same SQLite schema as the existing ClinicLink gateway.
- Existing CLI workflows remain fully functional; the desktop app is additive.
- No breaking changes to the `PatientHandoff` model or mesh protocol.
