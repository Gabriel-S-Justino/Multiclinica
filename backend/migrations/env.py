import os

from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from backend.infrastructure import (
    messaging_models,  # noqa: F401
    portal_models,  # noqa: F401
    scheduling_models,  # noqa: F401
)
from backend.infrastructure.models import Base


def run_migrations() -> None:
    url = os.environ.get("MIGRATION_DATABASE_URL")
    if not url or not url.startswith("postgresql+psycopg://"):
        raise RuntimeError("Configure MIGRATION_DATABASE_URL para conexão direta PostgreSQL")
    engine = create_engine(
        url, poolclass=NullPool, hide_parameters=True, connect_args={"prepare_threshold": None}
    )
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


run_migrations()
