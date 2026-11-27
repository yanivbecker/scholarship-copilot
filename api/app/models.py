"""Imports every model module so Base.metadata knows about all tables.

Alembic's autogenerate compares Base.metadata with the database, so a model
that is never imported is invisible to it. Add each new models module here.
"""

from app.core.db import Base
from app.modules.users import models as users_models

__all__ = ["Base", "users_models"]
