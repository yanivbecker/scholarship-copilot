"""Turn service exceptions into HTTP responses, in one place.

Services raise plain Python errors and know nothing about HTTP. These handlers
map them to status codes, so routes don't need try/except everywhere.
"""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.modules.profile.catalog import FactValidationError, FieldErrorsError
from app.modules.profile.service import NotFoundError, StoryValidationError
from app.modules.resume.files import ResumeFileError
from app.modules.resume.service import ResumeNotFoundError
from app.modules.sources.service import (
    DuplicateSourceError,
    PasteError,
    SourceNotFoundError,
)
from app.modules.sources.url_safety import UnsafeURLError

type Handler = Callable[[Request, Exception], Awaitable[JSONResponse]]


def _detail(status_code: int) -> Handler:
    async def handler(_request: Request, exc: Exception) -> JSONResponse:
        # Messages are written to be user-facing (see the error classes).
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    return handler


async def _field_errors(_request: Request, exc: Exception) -> JSONResponse:
    field_errors = getattr(exc, "field_errors", {})
    return JSONResponse(
        status_code=422,
        content={"detail": str(exc), "field_errors": field_errors},
    )


_STATUS_BY_ERROR: dict[type[Exception], int] = {
    FactValidationError: 422,
    StoryValidationError: 422,
    UnsafeURLError: 422,
    PasteError: 422,
    ResumeFileError: 422,
    DuplicateSourceError: 409,
    NotFoundError: 404,
    SourceNotFoundError: 404,
    ResumeNotFoundError: 404,
}


def register_error_handlers(app: FastAPI) -> None:
    for error, status_code in _STATUS_BY_ERROR.items():
        app.add_exception_handler(error, _detail(status_code))
    # Onboarding and resume confirm also report which fields failed.
    app.add_exception_handler(FieldErrorsError, _field_errors)
