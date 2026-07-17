# Task 4 Report: Implement clinic mode service

## What was implemented

- Created `src/return42/cliniclink/desktop_sidecar/clinic_service.py`:
  - `require_clinic_token(authorization)` helper that strips an optional `Bearer ` prefix and validates the token against the `CLINIC_TOKEN` environment variable (default `clinic-local-token`).
  - `ClinicService` class that wraps a `HandoffStore` and exposes a FastAPI `APIRouter` with:
    - `GET /handoffs` — list handoffs, optional `status` filter
    - `GET /handoffs/{handoff_id}` — fetch a single handoff
    - `POST /handoffs/{handoff_id}/ack` — acknowledge a handoff
- Updated `src/return42/cliniclink/desktop_sidecar/app.py`:
  - Added `app.state.sidecar_db` and `app.state.sidecar_queue_db` placeholders.
  - Added a FastAPI `lifespan` handler that instantiates `ClinicService` from the configured db path and mounts its router under `/clinic` at startup.
- Updated `tests/test_desktop_sidecar_api.py`:
  - Wrapped the `client` fixture in `with TestClient(app) as client:` so that lifespan/startup events run and the clinic router is actually registered.
  - Added the brief's `test_clinic_handoff_flow` test.

`src/return42/cliniclink/desktop_sidecar/state.py` already contained the `service` field described in the brief, so no additional changes were required there.

## TDD evidence

### RED (failing test before implementation)

```text
$ .venv/bin/python -m pytest tests/test_desktop_sidecar_api.py::test_clinic_handoff_flow -v
...
>       assert r.status_code == 200
E       assert 404 == 200
E        +  where 404 = <Response [404 Not Found]>.status_code

tests/test_desktop_sidecar_api.py:44: AssertionError
```

The `/clinic/handoffs` endpoint returned 404 because it had not been mounted yet.

### GREEN (passing test after implementation)

```text
$ .venv/bin/python -m pytest tests/test_desktop_sidecar_api.py::test_clinic_handoff_flow -v

tests/test_desktop_sidecar_api.py::test_clinic_handoff_flow PASSED
========================= 1 passed, 1 warning in 0.95s =========================
```

## Test results

- Focused test: `tests/test_desktop_sidecar_api.py` — **3 passed**.
- Full suite: `tests/` — **143 passed, 1 warning** (pre-existing starlette/httpx deprecation warning from the test client).

## Files changed

- `src/return42/cliniclink/desktop_sidecar/clinic_service.py` (new)
- `src/return42/cliniclink/desktop_sidecar/app.py` (modified)
- `tests/test_desktop_sidecar_api.py` (modified)

## Commits

- `e844480` — `feat(cliniclink): sidecar clinic mode service`
- `66cdf22` — `style(cliniclink): remove unused imports and fix blank lines`

## Self-review findings

- Implementation matches the brief: the three `/clinic/handoffs*` endpoints are present, token-protected, and use the existing `HandoffStore`.
- The clinic router is mounted under `/clinic` so the frontend can prefix calls based on mode without runtime route replacement.
- Switched from `@app.on_event("startup")` to a `lifespan` context manager to avoid FastAPI deprecation warnings.
- The `client` fixture now enters the `TestClient` context so lifespan startup runs; this is required because the router is registered during startup.
- Removed an unused `os` import in the test file and an unused `FastAPI` import in `clinic_service.py`.
- No PHI is logged or exposed by the new endpoints.

## Issues / concerns

- The brief's sample `app.py` also referenced an `AmbulanceService`; that service does not yet exist and was not implemented as part of this task. Only the clinic router is mounted.
- `CLINICLINK_ADMIN_TOKEN` is set in the test but is not consumed by the sidecar clinic service; it appears to be intended for future gateway/admin flows.
- `ack_handoff` now returns HTTP 404 for an unknown handoff id (fixed during review); previously it let `ValueError` leak as a 500.


## Review fixes applied

- `src/return42/cliniclink/desktop_sidecar/state.py`
  - Added a docstring to `SidecarState` explaining the `service` field and its `repr=False` exclusion.
- `src/return42/cliniclink/desktop_sidecar/clinic_service.py`
  - Replaced plain `!=` token comparison with `hmac.compare_digest` for constant-time validation.
  - Added a `-> APIRouter` return type annotation to `ClinicService.get_router`.
  - Wrapped `store.acknowledge` in `ack_handoff` so a missing handoff now raises `HTTPException(status_code=404)` instead of leaking `ValueError` as a 500.
- `tests/test_desktop_sidecar_api.py`
  - Added negative-path tests:
    - invalid clinic token returns 403
    - missing handoff returns 404 for both `GET` and `POST /ack`
    - missing `Authorization` header returns 422
- Git history
  - Squashed the `style(cliniclink): remove unused imports and fix blank lines` commit into the feature commit so the task is represented by a single clean commit.

## Updated test results

- Focused test: `tests/test_desktop_sidecar_api.py` — **6 passed**.
- Full Python suite: `tests/` — **146 passed, 1 warning** (pre-existing starlette/httpx deprecation warning).
