from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSTZRANGE, ExcludeConstraint, Range
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from backend.infrastructure.models import Base


def tenant_fk(table: str, column: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(["tenant_id", column], [f"{table}.tenant_id", f"{table}.id"])


class ClinicRecord(Base):
    __abstract__ = True
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)

    @declared_attr.directive
    def __table_args__(cls) -> tuple[Any, ...]:
        return (UniqueConstraint("tenant_id", "id"),)


class Service(ClinicRecord):
    __tablename__ = "services"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "service_queue_id"],
            ["service_queues.tenant_id", "service_queues.id"],
            use_alter=True,
            name="services_queue_fk",
        ),
        CheckConstraint("duration_minutes BETWEEN 1 AND 720 AND step_minutes BETWEEN 1 AND 720"),
        CheckConstraint("buffer_before BETWEEN 0 AND 240 AND buffer_after BETWEEN 0 AND 240"),
        CheckConstraint(
            "min_notice_minutes >= 0 AND cancellation_notice_minutes >= 0 AND reschedule_notice_minutes >= 0"
        ),
        CheckConstraint(
            "horizon_days BETWEEN 1 AND 365 AND max_reschedules >= 0 AND hold_ttl_minutes BETWEEN 1 AND 60"
        ),
    )
    name: Mapped[str] = mapped_column(String(120))
    display_order: Mapped[int] = mapped_column(default=0)
    service_queue_id: Mapped[UUID | None] = mapped_column()
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_professional: Mapped[bool] = mapped_column(Boolean, default=True)
    policy_validated: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_birth_date: Mapped[bool] = mapped_column(Boolean, default=False)
    duration_minutes: Mapped[int] = mapped_column()
    step_minutes: Mapped[int] = mapped_column()
    buffer_before: Mapped[int] = mapped_column()
    buffer_after: Mapped[int] = mapped_column()
    min_notice_minutes: Mapped[int] = mapped_column()
    cancellation_notice_minutes: Mapped[int] = mapped_column()
    reschedule_notice_minutes: Mapped[int] = mapped_column()
    horizon_days: Mapped[int] = mapped_column()
    max_reschedules: Mapped[int] = mapped_column()
    hold_ttl_minutes: Mapped[int] = mapped_column(default=10)


class ProfessionalService(ClinicRecord):
    __tablename__ = "professional_services"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "professional_id", "service_id"),
        tenant_fk("professionals", "professional_id"),
        tenant_fk("services", "service_id"),
        CheckConstraint("duration_minutes IS NULL OR duration_minutes BETWEEN 1 AND 720"),
    )
    professional_id: Mapped[UUID] = mapped_column()
    service_id: Mapped[UUID] = mapped_column()
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    duration_minutes: Mapped[int | None] = mapped_column()


class ServiceResource(ClinicRecord):
    __tablename__ = "service_resources"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "service_id", "resource_id"),
        tenant_fk("services", "service_id"),
        tenant_fk("resources", "resource_id"),
    )
    service_id: Mapped[UUID] = mapped_column()
    resource_id: Mapped[UUID] = mapped_column()


class ProfessionalSchedule(ClinicRecord):
    __tablename__ = "professional_schedules"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        tenant_fk("professionals", "professional_id"),
        tenant_fk("units", "unit_id"),
        CheckConstraint("weekday BETWEEN 0 AND 6"),
        CheckConstraint("start_minute >= 0 AND start_minute < end_minute AND end_minute <= 1440"),
        CheckConstraint("valid_until IS NULL OR valid_until >= valid_from"),
    )
    professional_id: Mapped[UUID] = mapped_column(index=True)
    unit_id: Mapped[UUID] = mapped_column()
    weekday: Mapped[int] = mapped_column()
    start_minute: Mapped[int] = mapped_column()
    end_minute: Mapped[int] = mapped_column()
    valid_from: Mapped[date] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date)


class ScheduleException(ClinicRecord):
    __tablename__ = "schedule_exceptions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        tenant_fk("professionals", "professional_id"),
        tenant_fk("units", "unit_id"),
        CheckConstraint(
            "(closed AND start_minute IS NULL AND end_minute IS NULL) OR (NOT closed AND start_minute IS NOT NULL AND end_minute IS NOT NULL AND start_minute >= 0 AND end_minute > start_minute AND end_minute <= 1440)"
        ),
    )
    professional_id: Mapped[UUID] = mapped_column(index=True)
    unit_id: Mapped[UUID] = mapped_column()
    day: Mapped[date] = mapped_column(Date)
    closed: Mapped[bool] = mapped_column(Boolean)
    start_minute: Mapped[int | None] = mapped_column()
    end_minute: Mapped[int | None] = mapped_column()


class Holiday(ClinicRecord):
    __tablename__ = "holidays"
    __table_args__ = (UniqueConstraint("tenant_id", "id"), tenant_fk("units", "unit_id"))
    unit_id: Mapped[UUID | None] = mapped_column()
    day: Mapped[date] = mapped_column(Date, index=True)


class BlockedPeriod(ClinicRecord):
    __tablename__ = "blocked_periods"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        tenant_fk("units", "unit_id"),
        tenant_fk("professionals", "professional_id"),
        tenant_fk("resources", "resource_id"),
        CheckConstraint("ends_at > starts_at"),
    )
    unit_id: Mapped[UUID | None] = mapped_column()
    professional_id: Mapped[UUID | None] = mapped_column(index=True)
    resource_id: Mapped[UUID | None] = mapped_column()
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Contact(ClinicRecord):
    __tablename__ = "contacts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "phone_hash"),
    )
    phone_ciphertext: Mapped[str] = mapped_column(String(1024))
    phone_hash: Mapped[str] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Patient(ClinicRecord):
    __tablename__ = "patients"
    name_ciphertext: Mapped[str] = mapped_column(String(2048))
    birth_date_ciphertext: Mapped[str | None] = mapped_column(String(1024))


class ContactPatientLink(ClinicRecord):
    __tablename__ = "contact_patient_links"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "contact_id", "patient_id"),
        tenant_fk("contacts", "contact_id"),
        tenant_fk("patients", "patient_id"),
    )
    contact_id: Mapped[UUID] = mapped_column()
    patient_id: Mapped[UUID] = mapped_column()
    relationship: Mapped[str] = mapped_column(String(30))
    verification_method: Mapped[str | None] = mapped_column(String(30))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    verification_reference: Mapped[str | None] = mapped_column(String(80))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class Conversation(ClinicRecord):
    __tablename__ = "conversations"
    __table_args__ = (UniqueConstraint("tenant_id", "id"), tenant_fk("contacts", "contact_id"))
    contact_id: Mapped[UUID] = mapped_column()


class ConversationState(ClinicRecord):
    __tablename__ = "conversation_state"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "conversation_id"),
        tenant_fk("conversations", "conversation_id"),
        CheckConstraint("version >= 0"),
    )
    conversation_id: Mapped[UUID] = mapped_column()
    state: Mapped[str] = mapped_column(String(40))
    version: Mapped[int] = mapped_column(default=0)
    context: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class BookingFields:
    professional_id: Mapped[UUID] = mapped_column(index=True)
    service_id: Mapped[UUID] = mapped_column()
    unit_id: Mapped[UUID] = mapped_column()
    contact_id: Mapped[UUID] = mapped_column()
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_minutes: Mapped[int] = mapped_column()
    buffer_before: Mapped[int] = mapped_column()
    buffer_after: Mapped[int] = mapped_column()
    occupied_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    occupied_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    occupied_period: Mapped[Range[datetime]] = mapped_column(
        TSTZRANGE, Computed("tstzrange(occupied_start, occupied_end, '[)')", persisted=True)
    )


def booking_constraints() -> tuple[Any, ...]:
    return (
        UniqueConstraint("tenant_id", "id"),
        tenant_fk("professionals", "professional_id"),
        tenant_fk("services", "service_id"),
        tenant_fk("units", "unit_id"),
        tenant_fk("contacts", "contact_id"),
        CheckConstraint(
            "duration_minutes BETWEEN 1 AND 720 AND buffer_before BETWEEN 0 AND 240 AND buffer_after BETWEEN 0 AND 240"
        ),
        CheckConstraint(
            "ends_at = starts_at + duration_minutes * interval '1 minute' AND occupied_start = starts_at - buffer_before * interval '1 minute' AND occupied_end = ends_at + buffer_after * interval '1 minute'"
        ),
    )


class AppointmentHold(BookingFields, ClinicRecord):
    __tablename__ = "appointment_holds"
    __table_args__ = (
        *booking_constraints(),
        ForeignKeyConstraint(
            ["tenant_id", "replaces_appointment_id"],
            ["appointments.tenant_id", "appointments.id"],
            use_alter=True,
            name="hold_replacement_fk",
            deferrable=True,
            initially="DEFERRED",
        ),
        tenant_fk("conversations", "conversation_id"),
        CheckConstraint("state IN ('held','released','consumed')"),
        Index("ix_hold_active", "tenant_id", "professional_id", "expires_at"),
    )
    owner_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    state: Mapped[str] = mapped_column(String(20), default="held")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    conversation_id: Mapped[UUID | None] = mapped_column()
    replaces_appointment_id: Mapped[UUID | None] = mapped_column()


class Appointment(BookingFields, ClinicRecord):
    __tablename__ = "appointments"
    __table_args__ = (
        *booking_constraints(),
        tenant_fk("patients", "patient_id"),
        tenant_fk("appointment_holds", "source_hold_id"),
        ForeignKeyConstraint(
            ["tenant_id", "replaced_by_id"],
            ["appointments.tenant_id", "appointments.id"],
            deferrable=True,
            initially="DEFERRED",
        ),
        UniqueConstraint("tenant_id", "source_hold_id"),
        CheckConstraint(
            "status IN ('scheduled','confirmed','completed','canceled','no_show','rescheduled')"
        ),
        CheckConstraint("version >= 0 AND reschedule_count >= 0"),
        CheckConstraint("(status = 'rescheduled') = (replaced_by_id IS NOT NULL)"),
        ExcludeConstraint(
            ("tenant_id", "="),
            ("professional_id", "="),
            ("occupied_period", "&&"),
            using="gist",
            where=text("status IN ('scheduled','confirmed')"),
            name="appointments_no_overlap",
        ),
    )
    patient_id: Mapped[UUID] = mapped_column()
    source_hold_id: Mapped[UUID] = mapped_column()
    status: Mapped[str] = mapped_column(String(20), default="scheduled")
    version: Mapped[int] = mapped_column(default=0)
    reschedule_count: Mapped[int] = mapped_column(default=0)
    replaced_by_id: Mapped[UUID | None] = mapped_column()


class BookingResource(ClinicRecord):
    __tablename__ = "booking_resources"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        tenant_fk("resources", "resource_id"),
        tenant_fk("appointment_holds", "hold_id"),
        tenant_fk("appointments", "appointment_id"),
        CheckConstraint("(hold_id IS NOT NULL) <> (appointment_id IS NOT NULL)"),
        UniqueConstraint("tenant_id", "hold_id", "resource_id"),
        UniqueConstraint("tenant_id", "appointment_id", "resource_id"),
    )
    resource_id: Mapped[UUID] = mapped_column(index=True)
    hold_id: Mapped[UUID | None] = mapped_column()
    appointment_id: Mapped[UUID | None] = mapped_column()


class AppointmentTransition(ClinicRecord):
    __tablename__ = "appointment_transitions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        tenant_fk("appointments", "appointment_id"),
    )
    appointment_id: Mapped[UUID] = mapped_column()
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IdempotencyRecord(ClinicRecord):
    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("tenant_id", "id"), UniqueConstraint("tenant_id", "key"))
    key: Mapped[str] = mapped_column(String(128))
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    operation: Mapped[str] = mapped_column(String(30))
    request_hash: Mapped[str] = mapped_column(String(64))
    result: Mapped[dict[str, Any]] = mapped_column(JSONB)


class OutboxEvent(ClinicRecord):
    __tablename__ = "outbox"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "event_key"),
    )
    event_key: Mapped[str] = mapped_column(String(180))
    event_type: Mapped[str] = mapped_column(String(60))
    aggregate_id: Mapped[UUID] = mapped_column()
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="pending")
