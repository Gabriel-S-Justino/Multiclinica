from sqlalchemy import Engine, text

from backend.config import Settings
from backend.infrastructure.db import transaction
from backend.infrastructure.security import digest


def consume(engine: Engine, settings: Settings, scope: str, subject: str, limit: int) -> bool:
    # Separate commit: failed login transactions must not roll back abuse counters.
    with transaction(engine) as db:
        count = db.scalar(
            text("""
            INSERT INTO rate_limit_buckets (key, "window", count)
            VALUES (:key, floor(extract(epoch from clock_timestamp()) / 300)::bigint, 1)
            ON CONFLICT (key, "window") DO UPDATE
            SET count = rate_limit_buckets.count + 1 RETURNING count
        """),
            {"key": digest(settings, scope, subject)},
        )
        return bool(count is not None and count <= limit)
