"""Generated migrations must not import app code (they have to work forever)."""

from alembic.autogenerate import produce_migrations, render_python_code
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

from app.core.types import alembic_render_item
from app.models import Base


def test_app_types_render_as_plain_sqlalchemy() -> None:
    engine = create_engine("sqlite://")  # empty database: every table is "new"
    with engine.connect() as connection:
        context = MigrationContext.configure(
            connection, opts={"render_item": alembic_render_item}
        )
        script = produce_migrations(context, Base.metadata)
        assert script.upgrade_ops is not None
        code = render_python_code(script.upgrade_ops, render_item=alembic_render_item)

    assert "sa.DateTime(timezone=True)" in code
    assert "app." not in code
