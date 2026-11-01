from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.application.ai_quota import reserve, settle
from backend.infrastructure.messaging_models import AIUsage


def test_atomic_monthly_quota_and_idempotent_settlement(foundation):
    _, admin, ids, _, client = foundation
    engine = client.app.state.engine

    def attempt(index):
        with Session(engine) as db, db.begin():
            return reserve(
                db,
                ids["tenant"],
                f"test-request-{index}",
                "test-conversation",
                provider="synthetic",
                model="fixture",
                tokens=30,
                monthly_limit=100,
                conversation_limit=100,
            )

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(attempt, range(20)))
    winners = [item for item in results if item]
    assert len(winners) == 3
    with Session(engine) as db, db.begin():
        settle(db, ids["tenant"], winners[0], 20, succeeded=True)
        settle(db, ids["tenant"], winners[0], 20, succeeded=True)
        with pytest.raises(ValueError):
            settle(db, ids["tenant"], winners[0], 21, succeeded=True)
    with Session(admin) as db:
        rows = list(db.scalars(select(AIUsage)))
        assert sum(row.reserved_tokens for row in rows) == 90
        assert sum(row.used_tokens for row in rows) == 20


def test_quota_replay_and_tenant_isolation(foundation):
    _, _, ids, _, client = foundation
    engine = client.app.state.engine
    key = uuid4().hex
    args = dict(
        provider="synthetic", model="fixture", tokens=10, monthly_limit=100, conversation_limit=50
    )
    with Session(engine) as db, db.begin():
        item = reserve(db, ids["tenant"], key, "opaque", **args)
        assert item is not None
        assert reserve(db, ids["tenant"], key, "opaque", **args) is None
        with pytest.raises(ValueError):
            reserve(db, ids["tenant"], key, "different", **args)
        with pytest.raises(ValueError):
            settle(db, ids["other_tenant"], item, 5, succeeded=True)
