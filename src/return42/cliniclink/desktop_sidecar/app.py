from __future__ import annotations

from fastapi import FastAPI

from .state import STATE, SidecarMode


def create_sidecar_app() -> FastAPI:
    app = FastAPI(title="ClinicLink Desktop Sidecar", version="1.0.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/mode")
    def get_mode() -> dict[str, str | None]:
        return {"mode": STATE.mode.value if STATE.mode else None}

    @app.post("/mode")
    def set_mode(payload: dict[str, str]) -> dict[str, str | None]:
        mode = payload.get("mode")
        if mode not in {SidecarMode.CLINIC.value, SidecarMode.AMBULANCE.value}:
            raise ValueError("invalid mode")
        STATE.mode = SidecarMode(mode)
        return {"mode": STATE.mode.value}

    @app.get("/identity")
    def identity() -> dict[str, str | None]:
        return {"node_id": STATE.node_id, "verify_key_b64": STATE.verify_key_b64}

    return app
