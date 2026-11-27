"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.routing import APIRoute

from app import __version__
from app.api.dashboard import router as dashboard_router
from app.api.discovery import router as discovery_router
from app.api.eligibility import router as eligibility_router
from app.api.errors import register_error_handlers
from app.api.health import router as health_router
from app.api.packets import router as packets_router
from app.api.onboarding import router as onboarding_router
from app.api.profile import router as profile_router
from app.api.resume import router as resume_router
from app.api.scholarships import router as scholarships_router
from app.api.sources import router as sources_router
from app.api.stories import router as stories_router
from app.api.tracking import router as tracking_router

API_PREFIX = "/api/v1"


def _operation_id(route: APIRoute) -> str:
    # Use the Python function name ("list_facts") as the OpenAPI operation id,
    # so the generated TypeScript types get short, readable names.
    return route.name


def create_app() -> FastAPI:
    application = FastAPI(
        title="Scholarship Copilot API",
        version=__version__,
        generate_unique_id_function=_operation_id,
    )
    for router in (
        health_router,
        profile_router,
        onboarding_router,
        stories_router,
        resume_router,
        scholarships_router,
        eligibility_router,
        discovery_router,
        tracking_router,
        dashboard_router,
        packets_router,
        sources_router,
    ):
        application.include_router(router, prefix=API_PREFIX)
    register_error_handlers(application)
    return application


app = create_app()
