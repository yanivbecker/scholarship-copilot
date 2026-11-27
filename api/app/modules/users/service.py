"""The app has one user today (the owner). Auth arrives with the cloud phase.

Everything else takes a user_id, so adding real users later only changes how
the current user is found, not the rest of the code (NFR-8).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.users.models import User

DEFAULT_DISPLAY_NAME = "Me"


def get_or_create_owner(session: Session) -> User:
    """Return the single local user, creating it on first run."""
    owner = session.scalars(select(User).order_by(User.id)).first()
    if owner is None:
        owner = User(display_name=DEFAULT_DISPLAY_NAME)
        session.add(owner)
        session.flush()
    return owner
