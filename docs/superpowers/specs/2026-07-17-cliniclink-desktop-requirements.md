# ClinicLink Desktop Requirements

> **Status:** Draft awaiting review  
> **Date:** 2026-07-17  
> **Topic:** Requirements for the ClinicLink Desktop GUI  

## 1. Purpose

Define the requirements for a cross-platform desktop application that provides a graphical user interface for ClinicLink, enabling rural clinic staff and ambulance crews to exchange patient handoffs over the Return42 mesh without relying on cellular connectivity.

## 2. Stakeholders

| Role | Needs |
|------|-------|
| Rural clinic staff | Receive, view, and acknowledge incoming ambulance handoffs quickly and securely. |
| Ambulance crew | Create and send structured patient handoffs to the nearest trusted clinic. |
| IT/deployer | Install, configure, and update the application using familiar platform installers. |
| Administrator | Pre-enroll trust keys and audit handoff events without exposing PHI. |

## 3. User Stories

### Clinic Staff

- As a nurse, I want to see a new handoff alert immediately so that I can prepare for the incoming patient.
- As a clinician, I want to view vital signs, medications, chief complaint, and ETA so that I can triage effectively.
- As a clinician, I want to acknowledge a handoff with one click so that the ambulance crew knows the clinic is ready.
- As a clinic user, I want the app to work without internet access so that rural connectivity outages do not block patient care.

### Ambulance Crew

- As an EMT, I want to fill out a patient handoff form quickly so that I can focus on patient care.
- As a paramedic, I want the app to discover nearby clinics automatically so that I do not need to know network addresses.
- As a crew member, I want to see whether my handoff was delivered and acknowledged so that I know the clinic received it.
- As a crew member, I want unsent handoffs to queue and auto-send when a clinic is in range so that no handoff is lost.

### Administrator

- As an admin, I want to pre-enroll ambulance/clinic public keys so that only trusted nodes can exchange handoffs.
- As an admin, I want signing keys stored in OS secure storage so that they are not exposed in configuration files.
- As an auditor, I want non-PHI event logs so that I can trace operational issues without violating patient privacy.

## 4. Functional Requirements

### 4.1 Application Modes

| ID | Requirement | Priority |
|----|-------------|----------|
| F1 | The app shall support a Clinic mode and an Ambulance mode. | Must |
| F2 | The user shall select the mode on first launch and be able to change it later. | Must |
| F3 | Mode switching shall restart the sidecar services cleanly. | Must |

### 4.2 Clinic Mode

| ID | Requirement | Priority |
|----|-------------|----------|
| F4 | The app shall display a list of incoming handoffs sorted by arrival time. | Must |
| F5 | The app shall highlight pending handoffs and provide audible and visual alerts. | Must |
| F6 | The app shall show patient ID, chief complaint, vital signs, medications, ETA, ambulance ID, and status. | Must |
| F7 | The user shall acknowledge a handoff with one action and optional notes. | Must |
| F8 | The app shall indicate connection status to the local gateway and mesh. | Must |

### 4.3 Ambulance Mode

| ID | Requirement | Priority |
|----|-------------|----------|
| F9 | The app shall display discovered clinic gateways on the mesh. | Must |
| F10 | The user shall select a target clinic before sending a handoff. | Must |
| F11 | The app shall provide a form for patient ID, chief complaint, vital signs, medications, and ETA. | Must |
| F12 | The app shall submit the handoff to the selected clinic over the mesh. | Must |
| F13 | The app shall queue handoffs locally when no clinic is reachable and auto-send when one appears. | Must |
| F14 | The app shall show delivery status: queued, sent, acknowledged. | Must |

### 4.4 Real-Time Communication

| ID | Requirement | Priority |
|----|-------------|----------|
| F15 | The app shall maintain a persistent WebSocket connection to the sidecar for events. | Must |
| F16 | The frontend shall update immediately when a sidecar event arrives without polling. | Must |
| F17 | If the WebSocket drops, the app shall fall back to HTTP POST for commands and HTTP GET for state. | Must |

### 4.5 Security

| ID | Requirement | Priority |
|----|-------------|----------|
| F18 | Private signing keys shall never be exposed to the frontend. | Must |
| F19 | Signing keys and tokens shall be stored in OS secure storage. | Must |
| F20 | PHI shall not be persisted in browser storage or logs. | Must |
| F21 | The sidecar shall bind to loopback only. | Must |
| F22 | Mesh messages shall be signed and verified by the sidecar. | Must |

### 4.6 Packaging

| ID | Requirement | Priority |
|----|-------------|----------|
| F23 | The app shall be installable via platform-native installers on macOS, Windows, and Linux. | Must |
| F24 | The installers shall include the existing CLI binaries as the sidecar. | Must |
| F25 | The app shall check for updates and notify the user. | Should |

## 5. Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NF1 | New handoff alert latency from sidecar receive to UI display | < 1 second |
| NF2 | App startup time to interactive UI | < 5 seconds |
| NF3 | Supported platforms | macOS (arm64/x86_64), Windows (x86_64), Linux (x86_64) |
| NF4 | Concurrent handoffs handled without UI freeze | 100+ |
| NF5 | Offline/mesh-only operation | Must work with no WAN |
| NF6 | Accessibility | Keyboard-navigable, screen-reader friendly where feasible |
| NF7 | Install size | Reasonable for PyInstaller + Tauri bundle (< 200 MB per platform) |

## 6. Out of Scope

- Mobile apps (iOS/Android).
- Multi-clinic dispatch map/ETA dashboard (Phase 2).
- EHR integration (FHIR/HL7).
- SIP/voice bridge.
- Cloud sync or centralized server.

## 7. Acceptance Criteria

- A user in Ambulance mode can create and send a handoff that appears in a Clinic mode instance within mesh range.
- A clinic user can acknowledge the handoff, and the ambulance user sees the acknowledgement.
- The entire exchange works without cellular/WAN connectivity.
- All functional and non-functional requirements in this document are covered by automated tests.
