from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from sqlalchemy import Connection, Engine, create_engine, event, text
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


# Limites por transação (SET LOCAL também vale com o pooler da Neon, que ignora opções de
# conexão). A espera por bloqueios e consultas lentas falham com aviso em vez de segurar a
# função até o tempo máximo da Vercel.
TRANSACTION_LIMITS = (
    "SET LOCAL statement_timeout = '15s'",
    "SET LOCAL lock_timeout = '8s'",
    "SET LOCAL idle_in_transaction_session_timeout = '60s'",
)


def _apply_limits(_session: Session, _transaction: object, connection: Connection) -> None:
    if connection.dialect.name != "postgresql":
        return
    for statement in TRANSACTION_LIMITS:
        connection.exec_driver_sql(statement)


@contextmanager
def transaction(engine: Engine) -> Iterator[Session]:
    with Session(engine) as db:
        # Aplicados só quando a transação abre a conexão, para não conectar à toa.
        event.listen(db, "after_begin", _apply_limits)
        with db.begin():
            yield db
