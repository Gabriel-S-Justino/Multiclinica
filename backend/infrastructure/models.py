from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    LargeBinary,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    login: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    mfa_secret: Mapped[str | None] = mapped_column(String(512))
    last_totp_step: Mapped[int] = mapped_column(default=-1)
    is_service: Mapped[bool] = mapped_column(Boolean, default=False)


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120))
    timezone: Mapped[str] = mapped_column(String(64), default="America/Sao_Paulo")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(default=0)
    registration: Mapped[dict[str, str | None] | None] = mapped_column(JSONB)


class UserProfile(Base):
    __tablename__ = "user_profiles"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    details: Mapped[dict[str, str | None] | None] = mapped_column(JSONB)
    photo: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("tenant_id", "id"), UniqueConstraint("tenant_id", "user_id"))
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String(30))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    can_manage_schedule: Mapped[bool] = mapped_column(Boolean, default=False)


class Unit(Base):
    __tablename__ = "units"
    __table_args__ = (UniqueConstraint("tenant_id", "id"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Resource(Base):
    __tablename__ = "resources"
    __table_args__ = (
        CheckConstraint("capacity = 1", name="resource_unit_capacity"),
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(["tenant_id", "unit_id"], ["units.tenant_id", "units.id"]),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    unit_id: Mapped[UUID] = mapped_column()
    name: Mapped[str] = mapped_column(String(120))
    capacity: Mapped[int] = mapped_column(default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Professional(Base):
    __tablename__ = "professionals"
    __table_args__ = (UniqueConstraint("tenant_id", "id"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    display_name: Mapped[str] = mapped_column(String(120))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class ProfessionalAssignment(Base):
    __tablename__ = "professional_assignments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "membership_id"], ["memberships.tenant_id", "memberships.id"]
        ),
        ForeignKeyConstraint(
            ["tenant_id", "professional_id"], ["professionals.tenant_id", "professionals.id"]
        ),
    )
    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    membership_id: Mapped[UUID] = mapped_column(primary_key=True)
    professional_id: Mapped[UUID] = mapped_column(primary_key=True)


class PortalSession(Base):
    __tablename__ = "portal_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("memberships.id"))
    csrf_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    idle_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    authenticated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    mfa_verified: Mapped[bool] = mapped_column(Boolean)


class MFAChallenge(Base):
    __tablename__ = "mfa_challenges"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RecoveryToken(Base):
    __tablename__ = "recovery_tokens"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RateLimitBucket(Base):
    __tablename__ = "rate_limit_buckets"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    window: Mapped[int] = mapped_column(primary_key=True)
    count: Mapped[int] = mapped_column(default=1)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(80))
    resource_id: Mapped[UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    correlation_id: Mapped[UUID] = mapped_column(default=uuid4)
