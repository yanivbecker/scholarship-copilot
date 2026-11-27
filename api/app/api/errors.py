"""Turn service exceptions into HTTP responses, in one place.

Services raise plain Python errors and know nothing about HTTP. These handlers
map them to status codes, so routes don't need try/except everywhere.
"""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.modules.profile.catalog import FactValidationError
from app.modules.profile.onboarding import OnboardingError
from app.modules.profile.service import NotFoundError, StoryValidationError
from app.modules.sources.service import DuplicateSourceError, SourceNotFoundError
from app.modules.sources.url_safety import UnsafeURLError

type Handler = Callable[[Request, Exception], Awaitable[JSONResponse]]


def _detail(status_code: int) -> Handler:
    async def handler(_request: Request, exc: Exception) -> JSONResponse:
        # Messages are written to be user-facing (see the error classes).
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    return handler


async def _onboarding_error(_request: Request, exc: Exception) -> JSONResponse:
    field_errors = exc.field_errors if isinstance(exc, OnboardingError) else {}
    return JSONResponse(
        status_code=422,
        content={"detail": str(exc), "field_errors": field_errors},
    )


_STATUS_BY_ERROR: dict[type[Exception], int] = {
    FactValidationError: 422,
    StoryValidationError: 422,
    UnsafeURLError: 422,
    DuplicateSourceError: 409,
    NotFoundError: 404,
    SourceNotFoundError: 404,
}


def register_error_handlers(app: FastAPI) -> None:
    for error, status_code in _STATUS_BY_ERROR.items():
        app.add_exception_handler(error, _detail(status_code))
    # Onboarding also reports which fields failed.
    app.add_exception_handler(OnboardingError, _onboarding_error)
