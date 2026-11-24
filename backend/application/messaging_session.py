from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import Settings
from backend.domain.scheduling import SchedulingError
from backend.infrastructure.fields import seal
from backend.infrastructure.messaging_models import MessagingChannel, MessagingSession
from backend.infrastructure.scheduling_models import Contact, Conversation, ConversationState


def contact_session(
    db: Session,
    settings: Settings,
    channel: MessagingChannel,
    contact: Contact,
    last_inbound_at: datetime | None,
) -> MessagingSession:
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
            last_inbound_at=last_inbound_at,
        )
        db.add(session)
        db.flush()
    return session
