from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles


def mount_dashboard(app: FastAPI) -> None:
    static_dir = Path(__file__).parent / "static"
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
