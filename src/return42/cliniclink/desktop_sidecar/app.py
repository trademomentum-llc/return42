from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from .ambulance_service import AmbulanceService
from .clinic_service import ClinicService
from .state import STATE, SidecarMode
from .websocket import MANAGER


def _ensure_clinic_service(app: FastAPI) -> ClinicService:
    """Return the clinic service, creating and mounting it lazily if needed."""
    if not hasattr(app.state, "clinic_service"):
        clinic_service = ClinicService(db_path=app.state.sidecar_db, queue_db_path=app.state.sidecar_queue_db)
        app.include_router(clinic_service.get_router(), prefix="/clinic")
        app.state.clinic_service = clinic_service
    return app.state.clinic_service


def create_sidecar_app() -> FastAPI:
    """Create the ClinicLink desktop sidecar FastAPI application.

    Design note on clinic mode: the clinic sidecar does **not** start its own
    mesh receiver. Instead, it proxies REST/WS traffic to the local ClinicLink
    gateway (which is the canonical mesh receiver for the clinic) and shares a
    :class:`HandoffStore` with that gateway. Keeping mesh membership in the
    gateway avoids duplicating identity/trust state in the desktop process and
    keeps the sidecar focused on UI-facing orchestration.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        clinic_service = _ensure_clinic_service(app)
        STATE.service = clinic_service
        try:
            yield
        finally:
            if STATE.service is not None and hasattr(STATE.service, "stop"):
                await STATE.service.stop()

    app = FastAPI(title="ClinicLink Desktop Sidecar", version="1.0.0", lifespan=lifespan)
    app.state.sidecar_db = None
    app.state.sidecar_queue_db = None

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/mode")
    def get_mode() -> dict[str, str | None]:
        return {"mode": STATE.mode.value if STATE.mode else None}

    @app.post("/mode")
    async def set_mode(payload: dict[str, str]) -> dict[str, str | None]:
        mode = payload.get("mode")
        if mode not in {SidecarMode.CLINIC.value, SidecarMode.AMBULANCE.value}:
            raise ValueError("invalid mode")

        new_mode = SidecarMode(mode)
        if new_mode == SidecarMode.AMBULANCE and not isinstance(STATE.service, AmbulanceService):
            if STATE.service is not None and hasattr(STATE.service, "stop"):
                await STATE.service.stop()
            ambulance_service = AmbulanceService(
                db_path=app.state.sidecar_db, queue_db_path=app.state.sidecar_queue_db
            )
            await ambulance_service.start()
            app.include_router(ambulance_service.get_router(), prefix="/ambulance")
            STATE.service = ambulance_service

        if new_mode == SidecarMode.CLINIC and not isinstance(STATE.service, ClinicService):
            if STATE.service is not None and hasattr(STATE.service, "stop"):
                await STATE.service.stop()
            STATE.service = _ensure_clinic_service(app)

        STATE.mode = new_mode
        await MANAGER.broadcast("mode.changed", {"mode": STATE.mode.value})
        return {"mode": STATE.mode.value}

    @app.get("/identity")
    def identity() -> dict[str, str | None]:
        return {"node_id": STATE.node_id, "verify_key_b64": STATE.verify_key_b64}

    @app.websocket("/events")
    async def events(websocket: WebSocket) -> None:
        await MANAGER.connect(websocket)
        try:
            while True:
                # Keep connection open; optionally handle incoming commands
                data = await websocket.receive_text()
                # Echo as command.received for now; commands handled in later task
                await MANAGER.broadcast("command.received", {"data": data})
        except WebSocketDisconnect:
            MANAGER.disconnect(websocket)

    return app
