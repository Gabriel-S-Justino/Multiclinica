"""Atomic token reservations. No prompts or model outputs are retained."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import case, func, select, text
from sqlalchemy.orm import Session

from backend.infrastructure.db import set_tenant
from backend.infrastructure.messaging_models import AIUsage


def reserve(
    db: Session,
    tenant_id: UUID,
    request_key: str,
    conversation_key: str,
    *,
    provider: str,
    model: str,
    tokens: int,
    monthly_limit: int,
    conversation_limit: int,
) -> UUID | None:
    if (
        not 1 <= tokens <= 32000
        or not 1 <= monthly_limit <= 1000000000
        or not tokens <= conversation_limit <= monthly_limit
        or not 8 <= len(request_key) <= 128
        or not 1 <= len(conversation_key) <= 64
        or not 1 <= len(provider) <= 80
        or not 1 <= len(model) <= 120
    ):
        raise ValueError("invalid_ai_quota")
    set_tenant(db, tenant_id)
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:scope, 0))"),
        {"scope": f"ai-quota:{tenant_id}"},
    )
    moment = db.scalar(select(func.clock_timestamp()))
    if not isinstance(moment, datetime):
        raise RuntimeError("clock_unavailable")
    period = moment.strftime("%Y-%m")
    existing = db.scalar(
        select(AIUsage).where(AIUsage.tenant_id == tenant_id, AIUsage.request_key == request_key)
    )
    if existing:
        if (
            existing.conversation_key,
            existing.provider,
            existing.model,
            existing.reserved_tokens,
        ) != (conversation_key, provider, model, tokens):
            raise ValueError("quota_idempotency_conflict")
        # A reserved/complete request must never authorize a second provider call.
        return None
    # Reservas em andamento contam pelo valor reservado; chamadas concluídas ou com falha
    # contam pelo que o provedor realmente usou (falhas sem resposta não consomem cota).
    charged = func.coalesce(
        func.sum(
            case(
                (AIUsage.status == "reserved", AIUsage.reserved_tokens),
                else_=AIUsage.used_tokens,
            )
        ),
        0,
    )
    total = (
        db.scalar(select(charged).where(AIUsage.tenant_id == tenant_id, AIUsage.period == period))
        or 0
    )
    # O limite por conversa vale por contato e por mês, não para sempre.
    conversation = (
        db.scalar(
            select(charged).where(
                AIUsage.tenant_id == tenant_id,
                AIUsage.conversation_key == conversation_key,
                AIUsage.period == period,
            )
        )
        or 0
    )
    if total + tokens > monthly_limit or conversation + tokens > conversation_limit:
        return None
    row_id = uuid4()
    db.add(
        AIUsage(
            id=row_id,
            tenant_id=tenant_id,
            request_key=request_key,
            conversation_key=conversation_key,
            period=period,
            provider=provider,
            model=model,
            reserved_tokens=tokens,
            used_tokens=0,
            status="reserved",
            created_at=moment,
        )
    )
    db.flush()
    return row_id


def settle(
    db: Session, tenant_id: UUID, reservation_id: UUID, used_tokens: int, *, succeeded: bool
) -> None:
    set_tenant(db, tenant_id)
    row = db.scalar(
        select(AIUsage)
        .where(AIUsage.tenant_id == tenant_id, AIUsage.id == reservation_id)
        .with_for_update()
    )
    if not row or not 0 <= used_tokens <= row.reserved_tokens:
        raise ValueError("invalid_usage")
    target = "complete" if succeeded else "failed"
    if row.status != "reserved":
        if row.status != target or row.used_tokens != used_tokens:
            raise ValueError("usage_conflict")
        return
    row.used_tokens, row.status = used_tokens, target
