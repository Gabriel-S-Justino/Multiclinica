import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session

from backend.application.messaging_flow import Flow
from backend.application.messaging_intent import menu_intent
from backend.application.webhooks import channel_for, credentials
from backend.config import Settings
from backend.domain.scheduling import SchedulingError
from backend.infrastructure.db import transaction
from backend.infrastructure.fields import seal, unseal
from backend.infrastructure.messaging_models import (
    Dispatch,
    InboundJob,
    MessagingChannel,
    MessagingSession,
)
from backend.infrastructure.models import AuditLog
from backend.infrastructure.portal_models import Message
from backend.infrastructure.scheduling_models import (
    Contact,
    Conversation,
    ConversationState,
    OutboxEvent,
)
from backend.infrastructure.security import digest
from backend.infrastructure.whatsapp import CloudAPI, ProviderFailure, WhatsAppProvider


def lock_channel(db: Session, channel_id: UUID) -> MessagingChannel:
    channel = channel_for(db, channel_id)
    db.execute(text("SELECT public.lock_schedule(:tenant)"), {"tenant": channel.tenant_id})
    return channel


def now(db: Session) -> datetime:
    value = db.scalar(select(func.clock_timestamp()))
    if not isinstance(value, datetime):
        raise RuntimeError("clock_unavailable")
    return value


def session_for(
    db: Session,
    settings: Settings,
    channel: MessagingChannel,
    payload: dict[str, Any],
    moment: datetime,
) -> tuple[MessagingSession, ConversationState]:
    phone = payload["phone"]
    phone_hash = digest(settings, f"contact:{channel.tenant_id}", phone)
    contact = db.scalar(
        select(Contact).where(
            Contact.tenant_id == channel.tenant_id, Contact.phone_hash == phone_hash
        )
    )
    if not contact:
        row_id = uuid4()
        contact = Contact(
            id=row_id,
            tenant_id=channel.tenant_id,
            phone_hash=phone_hash,
            phone_ciphertext=seal(settings, channel.tenant_id, "contact", row_id, "phone", phone),
        )
        db.add(contact)
        db.flush()
    if not contact.active:
        raise SchedulingError("contact_unavailable")
    session = db.scalar(
        select(MessagingSession).where(
            MessagingSession.tenant_id == channel.tenant_id,
            MessagingSession.channel_id == channel.id,
            MessagingSession.contact_id == contact.id,
        )
    )
    if not session:
        active = list(
            db.execute(
                select(Conversation, ConversationState)
                .join(
                    ConversationState,
                    (Conversation.id == ConversationState.conversation_id)
                    & (Conversation.tenant_id == ConversationState.tenant_id),
                )
                .where(
                    Conversation.tenant_id == channel.tenant_id,
                    Conversation.contact_id == contact.id,
                    ConversationState.state != "DONE",
                )
                .with_for_update()
            )
        )
        if len(active) > 1:
            raise SchedulingError("conversation_conflict")
        if active:
            conversation, state = active[0]
        else:
            conversation = Conversation(
                id=uuid4(), tenant_id=channel.tenant_id, contact_id=contact.id
            )
            db.add(conversation)
            db.flush()
            state = ConversationState(
                tenant_id=channel.tenant_id,
                conversation_id=conversation.id,
                state="START",
                version=0,
                context={},
            )
            db.add(state)
        row_id = uuid4()
        session = MessagingSession(
            id=row_id,
            tenant_id=channel.tenant_id,
            channel_id=channel.id,
            contact_id=contact.id,
            conversation_id=conversation.id,
            context_ciphertext=seal(
                settings, channel.tenant_id, "messaging_session", row_id, "context", "{}"
            ),
            last_inbound_at=moment,
        )
        db.add(session)
        db.flush()
    state = db.scalar(
        select(ConversationState)
        .where(
            ConversationState.tenant_id == channel.tenant_id,
            ConversationState.conversation_id == session.conversation_id,
        )
        .with_for_update()
    )
    if not state:
        raise SchedulingError("conversation_conflict")
    return session, state


def callback(db: Session, channel: MessagingChannel, payload: dict[str, Any]) -> bool:
    row = db.scalar(
        select(Dispatch)
        .join(MessagingSession, MessagingSession.id == Dispatch.session_id)
        .where(
            Dispatch.tenant_id == channel.tenant_id,
            MessagingSession.channel_id == channel.id,
            Dispatch.provider_id == payload["id"],
        )
        .with_for_update()
    )
    if not row:
        return False
    rank = {
        "pending": 0,
        "sending": 0,
        "unknown": 0,
        "sent": 1,
        "failed": 1,
        "delivered": 2,
        "read": 3,
    }
    target = payload["status"]
    if rank.get(target, 0) > rank.get(row.status, 0) or (
        target == "failed" and row.status == "sent"
    ):
        row.status = target
        message = db.get(Message, row.message_id)
        if message:
            message.delivery_status = target
    return True


def process_one(engine: Engine, settings: Settings, channel_id: UUID) -> bool:
    with transaction(engine) as db:
        channel = lock_channel(db, channel_id)
        moment = now(db)
        # Earliest event first. A delayed retry blocks later events in this channel.
        job = db.scalar(
            select(InboundJob)
            .where(
                InboundJob.channel_id == channel.id,
                InboundJob.tenant_id == channel.tenant_id,
                InboundJob.status == "pending",
            )
            .order_by(InboundJob.sequence)
            .limit(1)
            .with_for_update()
        )
        if not job or job.available_at > moment:
            return False
        job.attempts += 1
        try:
            with db.begin_nested():
                payload = json.loads(
                    unseal(
                        settings,
                        channel.tenant_id,
                        "inbound",
                        job.id,
                        "payload",
                        job.payload_ciphertext,
                    )
                )
                if job.kind == "status":
                    if not callback(db, channel, payload):
                        raise SchedulingError("status_unmatched")
                else:
                    provider_at = datetime.fromtimestamp(payload["timestamp"], UTC)
                    if provider_at > moment + timedelta(minutes=5):
                        raise SchedulingError("invalid_timestamp")
                    session, state = session_for(db, settings, channel, payload, provider_at)
                    message_id = uuid4()
                    db.add(
                        Message(
                            id=message_id,
                            tenant_id=channel.tenant_id,
                            conversation_id=session.conversation_id,
                            body_ciphertext=seal(
                                settings,
                                channel.tenant_id,
                                "message",
                                message_id,
                                "body",
                                payload["text"]
                                if payload["type"] == "text"
                                else "[Tipo de mensagem não suportado]",
                            ),
                            direction="inbound",
                            delivery_status="received",
                            created_at=provider_at,
                        )
                    )
                    session.last_inbound_at = max(session.last_inbound_at, provider_at)
                    flow = Flow(db, settings, channel, session, state, moment, str(job.id))
                    if session.last_provider_at and provider_at < session.last_provider_at:
                        if state.state != "HUMAN_HANDOFF" and not session.opted_out:
                            flow.say(
                                "Recebemos uma mensagem anterior. Reconfirme a opção mais recente ou envie menu."
                            )
                    else:
                        try:
                            with db.begin_nested():
                                flow.handle(
                                    payload["text"],
                                    payload["type"],
                                    lambda message: menu_intent(
                                        db,
                                        engine,
                                        settings,
                                        channel.tenant_id,
                                        session.id,
                                        str(job.id),
                                        message,
                                    ),
                                )
                                db.flush()
                        except (SchedulingError, ValidationError, ValueError):
                            db.expire_all()
                            flow = Flow(db, settings, channel, session, state, moment, str(job.id))
                            flow.say(
                                "Não foi possível concluir essa etapa. O agendamento não foi alterado. Envie menu para recomeçar ou humano para atendimento."
                            )
                        session.last_provider_at = provider_at
                    flow.save()
                job.status, job.error_code = "done", None
        except SchedulingError as error:
            job.error_code = error.code
            job.available_at = moment + timedelta(
                seconds=min(300, 2**job.attempts) + secrets.randbelow(3)
            )
            if job.attempts >= 8:
                job.status = "dead"
        except Exception:
            # Driver/provider strings may include sensitive values; never persist them.
            job.error_code = "processing_failed"
            job.available_at = moment + timedelta(seconds=min(300, 2**job.attempts))
            if job.attempts >= 8:
                job.status = "dead"
        return True


def bridge_replies(db: Session, channel: MessagingChannel, moment: datetime) -> None:
    rows = list(
        db.scalars(
            select(OutboxEvent)
            .where(
                OutboxEvent.tenant_id == channel.tenant_id,
                OutboxEvent.event_type == "message.send",
                OutboxEvent.status == "pending",
            )
            .order_by(OutboxEvent.created_at)
            .limit(50)
            .with_for_update()
        )
    )
    for event in rows:
        message = db.get(Message, event.aggregate_id)
        if not message:
            event.status = "dead"
            continue
        session = db.scalar(
            select(MessagingSession).where(
                MessagingSession.tenant_id == channel.tenant_id,
                MessagingSession.channel_id == channel.id,
                MessagingSession.conversation_id == message.conversation_id,
            )
        )
        if not session:
            continue  # no inbound user window; do not invent a recipient/window
        if not db.scalar(
            select(Dispatch.id).where(
                Dispatch.tenant_id == channel.tenant_id, Dispatch.message_id == message.id
            )
        ):
            db.add(
                Dispatch(
                    tenant_id=channel.tenant_id,
                    message_id=message.id,
                    session_id=session.id,
                    available_at=moment,
                )
            )
        event.status = "done"


def send_one(
    engine: Engine, settings: Settings, channel_id: UUID, provider: WhatsAppProvider | None = None
) -> bool:
    with transaction(engine) as db:
        channel = lock_channel(db, channel_id)
        moment = now(db)
        bridge_replies(db, channel, moment)
        expired = list(
            db.scalars(
                select(Dispatch)
                .join(MessagingSession, MessagingSession.id == Dispatch.session_id)
                .where(
                    Dispatch.tenant_id == channel.tenant_id,
                    MessagingSession.channel_id == channel.id,
                    Dispatch.status == "sending",
                    Dispatch.lease_until <= moment,
                )
            )
        )
        for expired_row in expired:
            expired_row.status, expired_row.error_code = "unknown", "lease_expired"
            message = db.get(Message, expired_row.message_id)
            if message:
                message.delivery_status = "unknown"
        row = db.scalar(
            select(Dispatch)
            .join(MessagingSession, MessagingSession.id == Dispatch.session_id)
            .where(
                Dispatch.tenant_id == channel.tenant_id,
                MessagingSession.channel_id == channel.id,
                Dispatch.status == "pending",
                Dispatch.available_at <= moment,
            )
            .order_by(Dispatch.available_at, Dispatch.id)
            .limit(1)
            .with_for_update()
        )
        if not row:
            return False
        session, message = db.get(MessagingSession, row.session_id), db.get(Message, row.message_id)
        if not session or not message:
            row.status, row.error_code = "dead", "message_unavailable"
            return True
        contact = db.get(Contact, session.contact_id)
        if (
            not contact
            or not contact.active
            or session.opted_out
            or moment >= session.last_inbound_at + timedelta(hours=24)
        ):
            row.status, row.error_code, message.delivery_status = (
                "blocked",
                "window_or_consent",
                "blocked",
            )
            return True
        if not channel.send_enabled:
            return False  # remains queued; no fake delivery success in disabled mode
        if provider is None:
            if not channel.graph_version:
                return False
            provider = CloudAPI(
                channel.phone_number_id,
                channel.graph_version,
                credentials(db, settings, channel)["access_token"],
            )
        destination = unseal(
            settings, channel.tenant_id, "contact", contact.id, "phone", contact.phone_ciphertext
        )
        content = unseal(
            settings, channel.tenant_id, "message", message.id, "body", message.body_ciphertext
        )
        dispatch_id, tenant_id, actor_id = row.id, channel.tenant_id, channel.actor_user_id
        row.status, row.attempts, row.lease_until = (
            "sending",
            row.attempts + 1,
            moment + timedelta(seconds=60),
        )
        # Persist intent before I/O. Crash afterwards is unknown, never automatic resend.
    result, failure = None, None
    try:
        result = provider.send_text(destination, content)
    except ProviderFailure as error:
        failure = error
    except Exception:
        failure = ProviderFailure("delivery_unknown", ambiguous=True)
    with transaction(engine) as db:
        lock_channel(db, channel_id)
        completed = db.get(Dispatch, dispatch_id)
        if not completed or completed.tenant_id != tenant_id or completed.status != "sending":
            return True
        row = completed
        message = db.get(Message, row.message_id)
        if failure:
            row.error_code = failure.code
            row.status = (
                "unknown"
                if failure.ambiguous
                else "pending"
                if failure.retryable and row.attempts < 5
                else "dead"
            )
            row.available_at = now(db) + timedelta(
                seconds=min(300, 2**row.attempts) + secrets.randbelow(5)
            )
        else:
            row.provider_id, row.status, row.error_code = result, "sent", None
        if message:
            message.delivery_status = row.status
        db.add(
            AuditLog(
                tenant_id=tenant_id,
                actor_id=actor_id,
                action=f"message.{row.status}",
                resource_id=row.message_id,
                created_at=now(db),
            )
        )
    return True
