"""FastAPI application factory."""

from fastapi import FastAPI

from app import __version__
from app.api.health import router as health_router

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    application = FastAPI(title="Scholarship Copilot API", version=__version__)
    application.include_router(health_router, prefix=API_PREFIX)
    return application


app = create_app()
