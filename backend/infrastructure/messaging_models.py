from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.models import Base
from backend.infrastructure.scheduling_models import ClinicRecord, tenant_fk


class MessagingChannel(Base):
    __tablename__ = "messaging_channels"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), unique=True)
    phone_number_id: Mapped[str] = mapped_column(String(80), unique=True)
    account_id: Mapped[str] = mapped_column(String(80))
    actor_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    actor_membership_id: Mapped[UUID] = mapped_column(ForeignKey("memberships.id"))
    default_queue_id: Mapped[UUID] = mapped_column()
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    send_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    graph_version: Mapped[str | None] = mapped_column(String(12))
    idle_minutes: Mapped[int] = mapped_column(default=30)
    ambiguity_limit: Mapped[int] = mapped_column(default=3)


class MessagingSession(ClinicRecord):
    __tablename__ = "messaging_sessions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "channel_id", "contact_id"),
        tenant_fk("contacts", "contact_id"),
        tenant_fk("conversations", "conversation_id"),
    )
    channel_id: Mapped[UUID] = mapped_column(ForeignKey("messaging_channels.id"))
    contact_id: Mapped[UUID] = mapped_column()
    conversation_id: Mapped[UUID] = mapped_column()
    context_ciphertext: Mapped[str] = mapped_column(Text)
    last_inbound_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_provider_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opted_out: Mapped[bool] = mapped_column(Boolean, default=False)


class InboundJob(ClinicRecord):
    __tablename__ = "inbound_jobs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("channel_id", "event_key"),
        CheckConstraint("status IN ('pending','done','dead')"),
    )
    sequence: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True)
    channel_id: Mapped[UUID] = mapped_column(ForeignKey("messaging_channels.id"))
    event_key: Mapped[str] = mapped_column(String(180))
    kind: Mapped[str] = mapped_column(String(20))
    payload_ciphertext: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    attempts: Mapped[int] = mapped_column(default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(60))


class Dispatch(ClinicRecord):
    __tablename__ = "message_dispatches"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "message_id"),
        tenant_fk("messages", "message_id"),
        tenant_fk("messaging_sessions", "session_id"),
        CheckConstraint(
            "status IN ('pending','sending','sent','delivered','read','failed','unknown','blocked','dead')"
        ),
    )
    message_id: Mapped[UUID] = mapped_column()
    session_id: Mapped[UUID] = mapped_column()
    provider_id: Mapped[str | None] = mapped_column(String(180), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    attempts: Mapped[int] = mapped_column(default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(60))


class AIUsage(ClinicRecord):
    __tablename__ = "ai_usage"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "request_key"),
        CheckConstraint(
            "reserved_tokens > 0 AND used_tokens >= 0 AND used_tokens <= reserved_tokens"
        ),
    )
    request_key: Mapped[str] = mapped_column(String(128))
    conversation_key: Mapped[str] = mapped_column(String(64))
    period: Mapped[str] = mapped_column(String(7))
    provider: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(120))
    reserved_tokens: Mapped[int] = mapped_column()
    used_tokens: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(20), default="reserved")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
