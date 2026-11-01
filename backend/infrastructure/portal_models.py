from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.models import Base
from backend.infrastructure.scheduling_models import ClinicRecord, tenant_fk


class ClinicPolicy(ClinicRecord):
    __tablename__ = "clinic_policies"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id"),
        CheckConstraint("verification_ttl_minutes BETWEEN 1 AND 10080"),
    )
    identity_policy_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    identity_policy_reference: Mapped[str] = mapped_column(String(80))
    verification_ttl_minutes: Mapped[int] = mapped_column()
    version: Mapped[int] = mapped_column(default=0)


class ServiceQueue(ClinicRecord):
    __tablename__ = "service_queues"
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(30))
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    hours: Mapped[list[dict[str, int]]] = mapped_column(JSONB, default=list)
    outside_hours_notice: Mapped[str] = mapped_column(String(300))
    version: Mapped[int] = mapped_column(default=0)


class QueueMembership(ClinicRecord):
    __tablename__ = "queue_memberships"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "queue_id", "membership_id"),
        tenant_fk("service_queues", "queue_id"),
        tenant_fk("memberships", "membership_id"),
    )
    queue_id: Mapped[UUID] = mapped_column()
    membership_id: Mapped[UUID] = mapped_column()


class Handoff(ClinicRecord):
    __tablename__ = "handoffs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        tenant_fk("conversations", "conversation_id"),
        tenant_fk("service_queues", "queue_id"),
        tenant_fk("memberships", "assignee_membership_id"),
        CheckConstraint("status IN ('waiting','assigned','released','closed')"),
        CheckConstraint("version >= 0"),
        Index(
            "handoff_one_open",
            "tenant_id",
            "conversation_id",
            unique=True,
            postgresql_where=text("status IN ('waiting','assigned')"),
        ),
    )
    conversation_id: Mapped[UUID] = mapped_column()
    queue_id: Mapped[UUID] = mapped_column()
    reason_code: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="waiting")
    assignee_membership_id: Mapped[UUID | None] = mapped_column()
    version: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Message(ClinicRecord):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        tenant_fk("conversations", "conversation_id"),
        CheckConstraint("direction IN ('inbound','outbound')"),
        Index("messages_conversation_page", "tenant_id", "conversation_id", "created_at", "id"),
    )
    conversation_id: Mapped[UUID] = mapped_column()
    body_ciphertext: Mapped[str] = mapped_column(Text)
    direction: Mapped[str] = mapped_column(String(20))
    delivery_status: Mapped[str] = mapped_column(String(20))
    sender_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IntegrationConfig(ClinicRecord):
    __tablename__ = "integration_configs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "provider"),
        CheckConstraint("provider IN ('whatsapp','ai')"),
    )
    provider: Mapped[str] = mapped_column(String(30))
    credentials_ciphertext: Mapped[str] = mapped_column(String(32768))
    version: Mapped[int] = mapped_column(default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PlatformOperator(Base):
    __tablename__ = "platform_operators"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class PlatformAudit(Base):
    __tablename__ = "platform_audit_logs"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"))
    action: Mapped[str] = mapped_column(String(80))
    resource_id: Mapped[UUID | None] = mapped_column()
    correlation_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class BreakGlassRequest(ClinicRecord):
    __tablename__ = "break_glass_requests"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint("duration_minutes BETWEEN 1 AND 15"),
        CheckConstraint("status IN ('pending','approved','rejected','revoked')"),
    )
    requester_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    appointment_id: Mapped[UUID] = mapped_column()
    reason_ciphertext: Mapped[str] = mapped_column(String(4096))
    duration_minutes: Mapped[int] = mapped_column()
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    version: Mapped[int] = mapped_column(default=0)


class AdminNotification(ClinicRecord):
    __tablename__ = "admin_notifications"
    notification_type: Mapped[str] = mapped_column(String(60))
    resource_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EntityVersion(ClinicRecord):
    __tablename__ = "entity_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "entity_type", "entity_id"),
    )
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[UUID] = mapped_column()
    version: Mapped[int] = mapped_column(default=0)


class Invitation(ClinicRecord):
    __tablename__ = "invitations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint("role IN ('collaborator','reception','admin')"),
        CheckConstraint("status IN ('pending','accepted','revoked')"),
    )
    recipient_hash: Mapped[str] = mapped_column(String(64), index=True)
    login_ciphertext: Mapped[str] = mapped_column(String(2048))
    role: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
