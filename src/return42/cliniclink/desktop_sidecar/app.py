from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from .clinic_service import ClinicService
from .state import STATE, SidecarMode
from .websocket import MANAGER


def create_sidecar_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        clinic_service = ClinicService(db_path=app.state.sidecar_db, queue_db_path=app.state.sidecar_queue_db)
        app.include_router(clinic_service.get_router(), prefix="/clinic")
        yield

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
        STATE.mode = SidecarMode(mode)
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
