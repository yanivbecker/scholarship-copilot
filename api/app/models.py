"""Imports every model module so Base.metadata knows about all tables.

Alembic's autogenerate compares Base.metadata with the database, so a model
that is never imported is invisible to it. Add each new models module here.
"""

from app.core.db import Base
from app.modules.documents import models as documents_models
from app.modules.eligibility import models as eligibility_models
from app.modules.profile import models as profile_models
from app.modules.scholarships import models as scholarships_models
from app.modules.sources import models as sources_models
from app.modules.users import models as users_models

__all__ = [
    "Base",
    "documents_models",
    "eligibility_models",
    "profile_models",
    "scholarships_models",
    "sources_models",
    "users_models",
]
