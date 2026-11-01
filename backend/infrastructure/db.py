from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from backend.config import Settings


def make_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.database_url.get_secret_value(),
        poolclass=NullPool,
        hide_parameters=True,
        connect_args={"prepare_threshold": None, "connect_timeout": 5},
    )


def set_tenant(db: Session, tenant_id: UUID) -> None:
    db.execute(
        text("SELECT set_config('app.tenant_id', :tenant, true)"), {"tenant": str(tenant_id)}
    )


@contextmanager
def transaction(engine: Engine) -> Iterator[Session]:
    with Session(engine) as db, db.begin():
        yield db
