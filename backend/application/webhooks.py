import hmac
import json
import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from backend.config import Settings
from backend.infrastructure.db import set_tenant
from backend.infrastructure.fields import seal, unseal
from backend.infrastructure.messaging_models import InboundJob, MessagingChannel
from backend.infrastructure.models import Tenant
from backend.infrastructure.portal_models import IntegrationConfig
from backend.infrastructure.whatsapp import verify_signature


def channel_for(db: Session, channel_id: UUID) -> MessagingChannel:
    channel = db.get(MessagingChannel, channel_id)
    if not channel or not channel.active:
        raise HTTPException(404, "channel_unavailable")
    set_tenant(db, channel.tenant_id)
    tenant = db.get(Tenant, channel.tenant_id)
    if not tenant or not tenant.active:
        raise HTTPException(404, "channel_unavailable")
    return channel


def credentials(db: Session, settings: Settings, channel: MessagingChannel) -> dict[str, str]:
    row = db.scalar(
        select(IntegrationConfig).where(
            IntegrationConfig.tenant_id == channel.tenant_id,
            IntegrationConfig.provider == "whatsapp",
        )
    )
    if not row:
        raise HTTPException(503, "channel_unconfigured")
    value: dict[str, str] = json.loads(
        unseal(
            settings,
            channel.tenant_id,
            "integration",
            row.id,
            "whatsapp",
            row.credentials_ciphertext,
        )
    )
    return value


def challenge(
    db: Session, settings: Settings, channel_id: UUID, mode: str, supplied: str, value: str
) -> str:
    channel = channel_for(db, channel_id)
    expected = credentials(db, settings, channel)["verify_token"]
    if (
        mode != "subscribe"
        or not hmac.compare_digest(expected.encode(), supplied.encode("utf-8", "replace"))
        or not re.fullmatch(r"[0-9]{1,100}", value)
    ):
        raise HTTPException(403, "verification_failed")
    # A Meta confirmou o endereço do webhook: o portal mostra a etapa como concluída.
    channel.webhook_verified_at = datetime.now(UTC)
    return value


def parse_events(payload: Any, channel: MessagingChannel) -> list[tuple[str, str, dict[str, Any]]]:
    events: list[tuple[str, str, dict[str, Any]]] = []
    if not isinstance(payload, dict) or payload.get("object") != "whatsapp_business_account":
        raise ValueError
    for entry in payload["entry"]:
        # Eventos de outra conta ou de outro número não pertencem a este canal: são
        # ignorados sem descartar os eventos válidos do mesmo lote.
        if entry["id"] != channel.account_id:
            continue
        for change in entry["changes"]:
            if change.get("field") != "messages":
                continue
            value = change["value"]
            if (
                value.get("messaging_product") != "whatsapp"
                or value["metadata"]["phone_number_id"] != channel.phone_number_id
            ):
                continue
            for message in value.get("messages", []):
                message_id, sender = message["id"], message["from"]
                if (
                    not isinstance(message_id, str)
                    or not 1 <= len(message_id) <= 150
                    or not re.fullmatch(r"[1-9][0-9]{7,14}", sender)
                ):
                    raise ValueError
                timestamp = int(message["timestamp"])
                body = (
                    message.get("text", {}).get("body", "") if message.get("type") == "text" else ""
                )
                if not isinstance(body, str) or len(body) > 4000 or timestamp < 0:
                    raise ValueError
                events.append(
                    (
                        f"message:{message_id}",
                        "message",
                        {
                            "phone": "+" + sender,
                            "timestamp": timestamp,
                            "type": message.get("type"),
                            "text": body,
                        },
                    )
                )
            for status in value.get("statuses", []):
                message_id, state = status["id"], status["status"]
                if not isinstance(message_id, str) or len(message_id) > 150:
                    raise ValueError
                if state not in {"sent", "delivered", "read", "failed"}:
                    continue  # novos estados da Meta não interrompem o lote
                events.append(
                    (f"status:{state}:{message_id}", "status", {"id": message_id, "status": state})
                )
    if len(events) > 100:
        raise ValueError
    return events


def ingest(
    db: Session, settings: Settings, channel_id: UUID, raw: bytes, signature: str, now: datetime
) -> None:
    channel = channel_for(db, channel_id)
    if len(raw) > 65536:
        raise HTTPException(413, "body_too_large")
    if not verify_signature(raw, signature, credentials(db, settings, channel)["app_secret"]):
        raise HTTPException(401, "signature_failed")
    try:
        events = parse_events(json.loads(raw), channel)
    except (ValueError, TypeError, KeyError, IndexError, OverflowError):
        raise HTTPException(400, "invalid_webhook") from None
    channel.last_event_at = now
    for key, kind, value in events:
        row_id = uuid4()
        encrypted = seal(
            settings, channel.tenant_id, "inbound", row_id, "payload", json.dumps(value)
        )
        db.execute(
            insert(InboundJob)
            .values(
                id=row_id,
                tenant_id=channel.tenant_id,
                channel_id=channel.id,
                event_key=key,
                kind=kind,
                payload_ciphertext=encrypted,
                status="pending",
                attempts=0,
                available_at=now,
            )
            .on_conflict_do_nothing(index_elements=["channel_id", "event_key"])
        )
