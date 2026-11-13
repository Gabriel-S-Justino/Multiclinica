import json
from uuid import UUID

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from backend.application import ai_quota
from backend.application.ai_boundary import (
    AIConfig,
    Intent,
    SafeTurn,
    eligible_turn,
    interpret_safely,
)
from backend.config import Settings
from backend.infrastructure.db import transaction
from backend.infrastructure.fields import unseal
from backend.infrastructure.openai_intent import OpenAIIntent
from backend.infrastructure.portal_models import IntegrationConfig

ALLOWED_INTENTS = frozenset(Intent)
RESERVED_TOKENS = 4096


def menu_intent(
    db: Session,
    engine: Engine,
    settings: Settings,
    tenant_id: UUID,
    session_id: UUID,
    event_key: str,
    message: str,
) -> Intent:
    turn = SafeTurn(message, "MENU", ALLOWED_INTENTS)
    if not eligible_turn(turn):
        return Intent.UNKNOWN
    row = db.scalar(
        select(IntegrationConfig).where(
            IntegrationConfig.tenant_id == tenant_id,
            IntegrationConfig.provider == "ai",
        )
    )
    if row is None:
        return Intent.UNKNOWN
    try:
        values = json.loads(
            unseal(
                settings,
                tenant_id,
                "integration",
                row.id,
                "ai",
                row.credentials_ciphertext,
            )
        )
        if values.get("enabled") != "true" or values.get("provider") != "openai":
            return Intent.UNKNOWN
        model = values["model"]
        config = AIConfig(
            enabled=True,
            provider="openai",
            model=model,
            data_policy_reference=values["data_policy_reference"],
            contract_reference=values["contract_reference"],
        )
        config.validate()
        provider = OpenAIIntent(model, values["api_key"])
        with transaction(engine) as usage:
            reservation = ai_quota.reserve(
                usage,
                tenant_id,
                event_key,
                str(session_id),
                provider="openai",
                model=model,
                tokens=RESERVED_TOKENS,
                monthly_limit=int(values["monthly_tokens"]),
                conversation_limit=int(values["conversation_tokens"]),
            )
        if reservation is None:
            return Intent.UNKNOWN
        result = interpret_safely(provider, config, turn, quota_reserved=True)
        with transaction(engine) as usage:
            ai_quota.settle(
                usage,
                tenant_id,
                reservation,
                min(provider.used_tokens, RESERVED_TOKENS),
                succeeded=result.intent != Intent.UNKNOWN,
            )
        return result.intent
    except Exception:
        # Storage and provider failures fall back to the menu without exposing text or credentials.
        return Intent.UNKNOWN
