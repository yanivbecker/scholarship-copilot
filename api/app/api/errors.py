"""Turn service exceptions into HTTP responses, in one place.

Services raise plain Python errors and know nothing about HTTP. These handlers
map them to status codes, so routes don't need try/except everywhere.
"""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.modules.profile.catalog import FactValidationError
from app.modules.profile.service import NotFoundError, StoryValidationError


type Handler = Callable[[Request, Exception], Awaitable[JSONResponse]]


def _detail(status_code: int) -> Handler:
    async def handler(_request: Request, exc: Exception) -> JSONResponse:
        # Messages are written to be user-facing (see the error classes).
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    return handler


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(FactValidationError, _detail(422))
    app.add_exception_handler(StoryValidationError, _detail(422))
    app.add_exception_handler(NotFoundError, _detail(404))
