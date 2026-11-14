"""Rotinas periódicas executadas pelo processador de mensagens (worker sempre ligado)."""

from sqlalchemy import Engine, text
from sqlalchemy.dialects.postgresql import insert

from backend.infrastructure.db import transaction
from backend.infrastructure.messaging_models import WorkerHeartbeat

WORKER_NAME = "messaging"
# Janelas de 5 minutos do limite de tentativas; uma hora de histórico basta para auditoria.
RATE_LIMIT_WINDOWS_KEPT = 12


def heartbeat(engine: Engine, name: str = WORKER_NAME) -> None:
    """Registra que o processador está vivo; o portal mostra esse estado ao dono da clínica."""
    with transaction(engine) as db:
        statement = insert(WorkerHeartbeat).values(name=name, seen_at=text("clock_timestamp()"))
        db.execute(
            statement.on_conflict_do_update(
                index_elements=["name"], set_={"seen_at": statement.excluded.seen_at}
            )
        )


def purge_expired(engine: Engine) -> dict[str, int]:
    """Apaga credenciais temporárias vencidas. Nenhum dado clínico é removido aqui."""
    statements = {
        "portal_sessions": (
            "DELETE FROM portal_sessions "
            "WHERE expires_at <= clock_timestamp() OR idle_expires_at <= clock_timestamp()"
        ),
        "mfa_challenges": "DELETE FROM mfa_challenges WHERE expires_at <= clock_timestamp()",
        "recovery_tokens": "DELETE FROM recovery_tokens WHERE expires_at <= clock_timestamp()",
        "rate_limit_buckets": (
            'DELETE FROM rate_limit_buckets WHERE "window" < '
            "floor(extract(epoch from clock_timestamp()) / 300)::bigint - :kept"
        ),
    }
    removed: dict[str, int] = {}
    with transaction(engine) as db:
        for table, sql in statements.items():
            result = db.execute(text(sql), {"kept": RATE_LIMIT_WINDOWS_KEPT})
            removed[table] = int(getattr(result, "rowcount", 0) or 0)
    return removed
