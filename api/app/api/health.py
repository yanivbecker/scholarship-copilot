"""Health check route. Routes stay thin: no business logic here."""

from fastapi import APIRouter
from pydantic import BaseModel

from app import __version__

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Response body for GET /api/v1/health."""

    status: str
    version: str


@router.get("/health")
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)
