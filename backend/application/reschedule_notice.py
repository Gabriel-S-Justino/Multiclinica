import json
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.application.messaging_session import contact_session
from backend.config import Settings
from backend.domain.scheduling import SchedulingError
from backend.infrastructure.fields import seal
from backend.infrastructure.messaging_models import MessagingChannel
from backend.infrastructure.models import Professional, Tenant
from backend.infrastructure.portal_models import Message
from backend.infrastructure.scheduling_models import Appointment, Contact, Conversation, OutboxEvent


def queue_reschedule_notice(
    db: Session,
    settings: Settings,
    appointment: Appointment,
    actor: UUID,
    moment: datetime,
    authorized: bool,
) -> None:
    tenant = db.get_one(Tenant, appointment.tenant_id)
    contact = db.get_one(Contact, appointment.contact_id)
    professional = db.get_one(Professional, appointment.professional_id)
    local = appointment.starts_at.astimezone(ZoneInfo(tenant.timezone))
    parameters = [professional.display_name, local.strftime("%d/%m/%Y"), local.strftime("%H:%M")]
    body = (
        f"Olá! Precisamos remarcar sua consulta com {parameters[0]}. "
        f"O novo horário é dia {parameters[1]}, às {parameters[2]} (horário da clínica). "
        "Se esse horário não funcionar para você, responda por aqui. Vamos ajudar!"
    )
    channel = db.scalar(
        select(MessagingChannel).where(
            MessagingChannel.tenant_id == tenant.id, MessagingChannel.active.is_(True)
        )
    )
    try:
        session = contact_session(db, settings, channel, contact, None) if channel else None
    except SchedulingError:
        # An ambiguous or unavailable conversation cannot receive a notice.
        session = None
    if session:
        conversation_id = session.conversation_id
    else:
        conversation = Conversation(tenant_id=tenant.id, contact_id=contact.id)
        db.add(conversation)
        db.flush()
        conversation_id = conversation.id
    message_id = uuid4()
    queued = bool(
        session
        and not session.opted_out
        and (
            authorized
            or (session.last_inbound_at and moment < session.last_inbound_at + timedelta(hours=24))
        )
    )
    db.add(
        Message(
            id=message_id,
            tenant_id=tenant.id,
            conversation_id=conversation_id,
            direction="outbound",
            sender_user_id=actor,
            created_at=moment,
            delivery_status="queued" if queued else "blocked",
            rescheduled_appointment_id=appointment.id,
            body_ciphertext=seal(settings, tenant.id, "message", message_id, "body", body),
            template_ciphertext=seal(
                settings, tenant.id, "message", message_id, "template", json.dumps(parameters)
            )
            if authorized
            else None,
        )
    )
    if queued:
        db.add(
            OutboxEvent(
                tenant_id=tenant.id,
                event_key=f"message:{message_id}",
                event_type="message.send",
                aggregate_id=message_id,
                payload={"message_id": str(message_id)},
                created_at=moment,
            )
        )
