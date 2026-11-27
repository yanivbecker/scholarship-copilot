"""Shared FastAPI dependencies, used as type annotations on route parameters."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.modules.users.models import User
from app.modules.users.service import get_or_create_owner

SessionDep = Annotated[Session, Depends(get_session)]


def get_current_user(session: SessionDep) -> User:
    """Today: the single local owner. With real auth, only this function changes."""
    return get_or_create_owner(session)


CurrentUser = Annotated[User, Depends(get_current_user)]
