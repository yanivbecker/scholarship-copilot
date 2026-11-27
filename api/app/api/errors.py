"""Turn service exceptions into HTTP responses, in one place.

Services raise plain Python errors and know nothing about HTTP. These handlers
map them to status codes, so routes don't need try/except everywhere.
"""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.ai.base import AIError, AIUnavailableError

from app.modules.background.launchd import BackgroundError
from app.modules.eligibility.service import CriterionNotFoundError, NotConfirmableError
from app.modules.packets.provenance import MaterialError
from app.modules.packets.rules import RulesError
from app.modules.packets.service import PacketError, PacketNotFoundError
from app.modules.packets.writing import AIHelpBlockedError
from app.modules.profile.catalog import FactValidationError, FieldErrorsError
from app.modules.profile.service import NotFoundError, StoryValidationError
from app.modules.resume.files import ResumeFileError
from app.modules.resume.service import ResumeNotFoundError
from app.modules.scholarships.merge import MergeError
from app.modules.settings.service import SettingsError
from app.modules.scholarships.service import ScholarshipNotFoundError
from app.modules.sources.service import (
    DuplicateSourceError,
    PasteError,
    ReviewError,
    SourceNotFoundError,
)
from app.modules.sources.url_safety import UnsafeURLError
from app.modules.tracking.service import StatusChangeError

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
    ReviewError: 422,
    NotConfirmableError: 422,
    MergeError: 422,
    StatusChangeError: 422,
    PacketError: 422,
    RulesError: 422,
    SettingsError: 422,
    BackgroundError: 502,  # launchctl refused; the message says why
    MaterialError: 422,
    AIHelpBlockedError: 403,
    AIUnavailableError: 503,  # AI turned off or unreachable: say how to proceed
    AIError: 502,  # refusal or unusable output
    ResumeFileError: 422,
    DuplicateSourceError: 409,
    NotFoundError: 404,
    SourceNotFoundError: 404,
    ResumeNotFoundError: 404,
    ScholarshipNotFoundError: 404,
    CriterionNotFoundError: 404,
    PacketNotFoundError: 404,
}


def register_error_handlers(app: FastAPI) -> None:
    for error, status_code in _STATUS_BY_ERROR.items():
        app.add_exception_handler(error, _detail(status_code))
    # Onboarding and resume confirm also report which fields failed.
    app.add_exception_handler(FieldErrorsError, _field_errors)
