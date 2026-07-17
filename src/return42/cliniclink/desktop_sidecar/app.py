from fastapi import FastAPI


def create_sidecar_app() -> FastAPI:
    """Factory for the ClinicLink desktop sidecar FastAPI application."""
    return FastAPI(title="ClinicLink Desktop Sidecar")
