from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.application.portal import read_professional, visible_professionals
from backend.application.scheduling_commands import (
    AppointmentMutation,
    AvailabilityQuery,
    ConfirmRequest,
    ContactRequest,
    HoldRequest,
    Mutation,
    NewPatient,
    ReleaseRequest,
    RescheduleRequest,
    TransitionRequest,
)
from backend.config import Settings
from backend.domain.permissions import ContactPrincipal, Principal
from backend.domain.scheduling import (
    ACTIVE_STATUSES,
    Interval,
    SchedulingError,
    candidate_slots,
    utc,
    validate_birth_date,
    validate_transition,
)
from backend.domain.selection import LeastFutureLoad, ProfessionalCandidate, SelectionStrategy
from backend.infrastructure.db import set_tenant
from backend.infrastructure.fields import seal
from backend.infrastructure.messaging_models import MessagingChannel
from backend.infrastructure.models import AuditLog, Membership, Resource, Tenant, Unit, User
from backend.infrastructure.scheduling_models import (
    Appointment,
    AppointmentHold,
    AppointmentTransition,
    BlockedPeriod,
    BookingResource,
    Contact,
    ContactPatientLink,
    Conversation,
    ConversationState,
    Holiday,
    IdempotencyRecord,
    OutboxEvent,
    Patient,
    ProfessionalSchedule,
    ProfessionalService,
    ScheduleException,
    Service,
    ServiceResource,
)
from backend.infrastructure.security import digest


@dataclass(frozen=True)
class Slot:
    professional_id: UUID
    start: datetime
    end: datetime


@dataclass(frozen=True)
class SlotPage:
    items: tuple[Slot, ...]
    next_offset: int | None


class Scheduler:
    """All writes run inside a caller-owned transaction; this class never commits.

    No network calls or patient names are present in returned/event payloads.
    Only server-resolved Principal identities may enter this application boundary.
    """

    def __init__(
        self,
        db: Session,
        settings: Settings,
        identity: Principal,
        strategy: SelectionStrategy | None = None,
    ) -> None:
        self.db, self.settings, self.identity = db, settings, identity
        self.strategy = strategy or LeastFutureLoad()
        self.selection_evidence: list[dict[str, Any]] = []

    @property
    def tenant_id(self) -> UUID:
        return self.identity.tenant_id

    def _authorize(self, *, lock: bool = False) -> datetime:
        set_tenant(self.db, self.tenant_id)
        if lock:
            self.db.execute(
                text("SELECT public.lock_schedule(:tenant)"), {"tenant": self.tenant_id}
            )
        # Reload authorization after waiting; a cached membership may have been revoked.
        member = self.db.scalar(
            select(Membership)
            .where(Membership.id == self.identity.membership_id)
            .execution_options(populate_existing=True)
        )
        user = self.db.scalar(
            select(User)
            .where(User.id == self.identity.user_id)
            .execution_options(populate_existing=True)
        )
        tenant = self.db.scalar(
            select(Tenant)
            .where(Tenant.id == self.tenant_id)
            .execution_options(populate_existing=True)
        )
        is_contact = isinstance(self.identity, ContactPrincipal)
        if isinstance(self.identity, ContactPrincipal):
            channel = self.db.get(MessagingChannel, self.identity.channel_id)
            if (
                not channel
                or not channel.active
                or channel.tenant_id != self.tenant_id
                or channel.actor_user_id != self.identity.user_id
                or channel.actor_membership_id != self.identity.membership_id
                or not self.identity.contact_id
            ):
                raise SchedulingError("permission_denied")
        if (
            not member
            or not member.active
            or member.user_id != self.identity.user_id
            or member.tenant_id != self.tenant_id
            or member.role != self.identity.role
            or member.role
            not in ({"messaging"} if is_contact else {"admin", "reception", "collaborator"})
            or not user
            or not user.active
            or (is_contact and not user.is_service)
            or not tenant
            or not tenant.active
            or (not is_contact and self.settings.mfa_required and not self.identity.mfa_verified)
        ):
            raise SchedulingError("permission_denied")
        # clock_timestamp, not transaction-start now(): a waiter must not reuse stale time.
        value = self.db.scalar(select(func.clock_timestamp()))
        if not isinstance(value, datetime):
            raise SchedulingError("clock_unavailable")
        return utc(value)

    def _service(self, service_id: UUID, *, require_active: bool = True) -> Service:
        item = self.db.scalar(
            select(Service).where(Service.tenant_id == self.tenant_id, Service.id == service_id)
        )
        if (
            not item
            or (require_active and not item.active)
            or not item.requires_professional
            or not item.policy_validated
        ):
            raise SchedulingError("service_unavailable")
        return item

    def _resources(self, service: Service, unit_id: UUID, requested: list[UUID]) -> list[UUID]:
        unit = self.db.scalar(
            select(Unit).where(
                Unit.tenant_id == self.tenant_id, Unit.id == unit_id, Unit.active.is_(True)
            )
        )
        if not unit:
            raise SchedulingError("unit_unavailable")
        required = self.db.scalars(
            select(ServiceResource.resource_id)
            .join(
                Resource,
                and_(
                    Resource.tenant_id == ServiceResource.tenant_id,
                    Resource.id == ServiceResource.resource_id,
                ),
            )
            .where(
                ServiceResource.tenant_id == self.tenant_id,
                ServiceResource.service_id == service.id,
                Resource.unit_id == unit_id,
            )
        )
        result = sorted(set(requested) | set(required), key=str)
        if result:
            valid = list(
                self.db.scalars(
                    select(Resource.id).where(
                        Resource.tenant_id == self.tenant_id,
                        Resource.unit_id == unit_id,
                        Resource.active.is_(True),
                        Resource.id.in_(result),
                    )
                )
            )
            if set(valid) != set(result):
                raise SchedulingError("resource_unavailable")
        return result

    def _duration(self, service: Service, professional_id: UUID) -> int:
        professional = read_professional(self.db, self.identity, professional_id)
        link = self.db.scalar(
            select(ProfessionalService).where(
                ProfessionalService.tenant_id == self.tenant_id,
                ProfessionalService.professional_id == professional_id,
                ProfessionalService.service_id == service.id,
                ProfessionalService.active.is_(True),
            )
        )
        if not professional or not professional.active or not link:
            raise SchedulingError("professional_unavailable")
        return link.duration_minutes or service.duration_minutes

    def _windows(self, professional_id: UUID, unit_id: UUID, day: date) -> list[tuple[int, int]]:
        holiday = self.db.scalar(
            select(Holiday.id)
            .where(
                Holiday.tenant_id == self.tenant_id,
                Holiday.day == day,
                or_(Holiday.unit_id.is_(None), Holiday.unit_id == unit_id),
            )
            .limit(1)
        )
        if holiday:
            return []
        exceptions = list(
            self.db.scalars(
                select(ScheduleException).where(
                    ScheduleException.tenant_id == self.tenant_id,
                    ScheduleException.professional_id == professional_id,
                    ScheduleException.unit_id == unit_id,
                    ScheduleException.day == day,
                )
            )
        )
        if exceptions:
            if any(item.closed for item in exceptions):
                return []
            return [
                (item.start_minute, item.end_minute)
                for item in exceptions
                if item.start_minute is not None and item.end_minute is not None
            ]
        schedules = self.db.scalars(
            select(ProfessionalSchedule).where(
                ProfessionalSchedule.tenant_id == self.tenant_id,
                ProfessionalSchedule.professional_id == professional_id,
                ProfessionalSchedule.unit_id == unit_id,
                ProfessionalSchedule.weekday == day.weekday(),
                ProfessionalSchedule.valid_from <= day,
                or_(
                    ProfessionalSchedule.valid_until.is_(None),
                    ProfessionalSchedule.valid_until >= day,
                ),
            )
        )
        return [(item.start_minute, item.end_minute) for item in schedules]

    def _busy(
        self,
        professional_id: UUID,
        unit_id: UUID,
        resources: list[UUID],
        now: datetime,
        exclude_hold: UUID | None = None,
        exclude_appointment: UUID | None = None,
    ) -> list[Interval]:
        result: list[Interval] = []
        resource_holds = select(BookingResource.hold_id).where(
            BookingResource.tenant_id == self.tenant_id,
            BookingResource.resource_id.in_(resources),
            BookingResource.hold_id.is_not(None),
        )
        resource_appointments = select(BookingResource.appointment_id).where(
            BookingResource.tenant_id == self.tenant_id,
            BookingResource.resource_id.in_(resources),
            BookingResource.appointment_id.is_not(None),
        )
        holds = self.db.scalars(
            select(AppointmentHold).where(
                AppointmentHold.tenant_id == self.tenant_id,
                AppointmentHold.state == "held",
                AppointmentHold.expires_at > now,
                or_(
                    AppointmentHold.professional_id == professional_id,
                    AppointmentHold.id.in_(resource_holds),
                ),
                AppointmentHold.id != exclude_hold if exclude_hold else text("true"),
            )
        )
        appointments = self.db.scalars(
            select(Appointment).where(
                Appointment.tenant_id == self.tenant_id,
                Appointment.status.in_(ACTIVE_STATUSES),
                or_(
                    Appointment.professional_id == professional_id,
                    Appointment.id.in_(resource_appointments),
                ),
                Appointment.id != exclude_appointment if exclude_appointment else text("true"),
            )
        )
        for item in [*holds, *appointments]:
            result.append(Interval(item.occupied_start, item.occupied_end))
        blocks = self.db.scalars(
            select(BlockedPeriod).where(
                BlockedPeriod.tenant_id == self.tenant_id,
                or_(BlockedPeriod.unit_id.is_(None), BlockedPeriod.unit_id == unit_id),
                or_(
                    BlockedPeriod.professional_id.is_(None),
                    BlockedPeriod.professional_id == professional_id,
                ),
                or_(BlockedPeriod.resource_id.is_(None), BlockedPeriod.resource_id.in_(resources)),
            )
        )
        result.extend(Interval(item.starts_at, item.ends_at) for item in blocks)
        return result

    def _slots(
        self,
        service: Service,
        unit_id: UUID,
        professional_id: UUID,
        day: date,
        resources: list[UUID],
        now: datetime,
        exclude_hold: UUID | None = None,
        exclude_appointment: UUID | None = None,
    ) -> list[Interval]:
        duration = self._duration(service, professional_id)
        tenant = self.db.get(Tenant, self.tenant_id)
        try:
            zone = ZoneInfo(tenant.timezone if tenant else "")
        except ZoneInfoNotFoundError as error:
            raise SchedulingError("invalid_timezone") from error
        local_today = now.astimezone(zone).date()
        if day < local_today or day > local_today + timedelta(days=service.horizon_days):
            return []
        return candidate_slots(
            day,
            zone,
            self._windows(professional_id, unit_id, day),
            duration,
            service.step_minutes,
            service.buffer_before,
            service.buffer_after,
            self._busy(professional_id, unit_id, resources, now, exclude_hold, exclude_appointment),
            now + timedelta(minutes=service.min_notice_minutes),
            now + timedelta(days=service.horizon_days),
        )

    def availability(self, query: AvailabilityQuery) -> SlotPage:
        now = self._authorize()
        service = self._service(query.service_id)
        resources = self._resources(service, query.unit_id, query.resource_ids)
        eligible = (
            [query.professional_id]
            if query.professional_id
            else [item.id for item in visible_professionals(self.db, self.identity) if item.active]
        )
        slots: list[Slot] = []
        for professional_id in eligible:
            try:
                self._duration(service, professional_id)
            except SchedulingError:
                if query.professional_id:
                    raise
                continue
            for offset in range((query.last_date - query.first_date).days + 1):
                day = query.first_date + timedelta(days=offset)
                slots.extend(
                    Slot(professional_id, value.start, value.end)
                    for value in self._slots(
                        service, query.unit_id, professional_id, day, resources, now
                    )
                )
        slots.sort(key=lambda item: (item.start, str(item.professional_id)))
        end = query.offset + query.limit
        return SlotPage(tuple(slots[query.offset : end]), end if end < len(slots) else None)

    def _request_hash(self, command: BaseModel) -> str:
        return digest(self.settings, "booking-request", command.model_dump_json())

    def _replay(self, operation: str, command: Mutation) -> dict[str, Any] | None:
        if (
            isinstance(self.identity, ContactPrincipal)
            and getattr(command, "contact_id", None) != self.identity.contact_id
        ):
            raise SchedulingError("identity_unverified")
        row = self.db.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.tenant_id == self.tenant_id,
                IdempotencyRecord.key == command.idempotency_key,
            )
        )
        if row:
            if (
                row.actor_id != self.identity.user_id
                or row.operation != operation
                or row.request_hash != self._request_hash(command)
            ):
                raise SchedulingError("idempotency_conflict")
            return dict(row.result)
        return None

    def _save(self, operation: str, command: Mutation, result: dict[str, Any]) -> dict[str, Any]:
        self.db.add(
            IdempotencyRecord(
                tenant_id=self.tenant_id,
                key=command.idempotency_key,
                actor_id=self.identity.user_id,
                operation=operation,
                request_hash=self._request_hash(command),
                result=result,
            )
        )
        self._flush()
        return result

    def _flush(self) -> None:
        try:
            self.db.flush()
        except IntegrityError as error:
            raise SchedulingError(
                "booking_conflict"
                if getattr(error.orig, "sqlstate", None) == "23P01"
                else "invalid_operation"
            ) from error

    def _contact(self, contact_id: UUID) -> Contact:
        if isinstance(self.identity, ContactPrincipal) and self.identity.contact_id != contact_id:
            raise SchedulingError("identity_unverified")
        value = self.db.scalar(
            select(Contact).where(
                Contact.tenant_id == self.tenant_id,
                Contact.id == contact_id,
                Contact.active.is_(True),
            )
        )
        if not value:
            raise SchedulingError("identity_unverified")
        return value

    def _verified_patient(self, contact_id: UUID, patient_id: UUID, now: datetime) -> Patient:
        self._contact(contact_id)
        link = self.db.scalar(
            select(ContactPatientLink).where(
                ContactPatientLink.tenant_id == self.tenant_id,
                ContactPatientLink.contact_id == contact_id,
                ContactPatientLink.patient_id == patient_id,
                ContactPatientLink.revoked.is_(False),
                ContactPatientLink.verification_method == "manual_clinic",
                ContactPatientLink.verified_by.is_not(None),
                ContactPatientLink.verified_at <= now,
                ContactPatientLink.verified_until > now,
            )
        )
        patient = self.db.scalar(
            select(Patient).where(Patient.tenant_id == self.tenant_id, Patient.id == patient_id)
        )
        if not link or not patient:
            raise SchedulingError("identity_unverified")
        return patient

    def _conversation(
        self,
        conversation_id: UUID | None,
        contact_id: UUID,
        version: int | None,
        expected_state: str,
        hold_id: UUID | None = None,
    ) -> ConversationState | None:
        if conversation_id is None:
            if version is not None:
                raise SchedulingError("conversation_conflict")
            return None
        conversation = self.db.scalar(
            select(Conversation).where(
                Conversation.tenant_id == self.tenant_id,
                Conversation.id == conversation_id,
                Conversation.contact_id == contact_id,
            )
        )
        state = self.db.scalar(
            select(ConversationState)
            .where(
                ConversationState.tenant_id == self.tenant_id,
                ConversationState.conversation_id == conversation_id,
            )
            .with_for_update()
        )
        if (
            not conversation
            or not state
            or state.version != version
            or state.state != expected_state
        ):
            raise SchedulingError("conversation_conflict")
        if hold_id and state.context.get("hold_id") != str(hold_id):
            raise SchedulingError("conversation_conflict")
        return state

    def _rank_professionals(
        self,
        service: Service,
        unit_id: UUID,
        start: datetime,
        resources: list[UUID],
        now: datetime,
        exclude_appointment: UUID | None = None,
    ) -> list[UUID]:
        tenant = self.db.get(Tenant, self.tenant_id)
        day = start.astimezone(ZoneInfo(tenant.timezone if tenant else "")).date()
        candidates: list[ProfessionalCandidate] = []
        for professional in visible_professionals(self.db, self.identity):
            if not professional.active:
                continue
            try:
                slots = self._slots(
                    service,
                    unit_id,
                    professional.id,
                    day,
                    resources,
                    now,
                    exclude_appointment=exclude_appointment,
                )
            except SchedulingError:
                continue
            if not any(slot.start == start for slot in slots):
                continue
            # Only future active minutes in the relevant search window, never history.
            appointments = self.db.scalars(
                select(Appointment).where(
                    Appointment.tenant_id == self.tenant_id,
                    Appointment.professional_id == professional.id,
                    Appointment.status.in_(ACTIVE_STATUSES),
                    Appointment.ends_at > now,
                    Appointment.starts_at < now + timedelta(days=service.horizon_days),
                )
            )
            load = sum(
                max(
                    0.0,
                    (
                        min(item.ends_at, now + timedelta(days=service.horizon_days))
                        - max(item.starts_at, now)
                    ).total_seconds(),
                )
                for item in appointments
            )
            candidates.append(ProfessionalCandidate(professional.id, load, slots[0].start))
        ranked = self.strategy.order(candidates)
        self.selection_evidence = [
            {
                "professional_id": str(item.professional_id),
                "future_seconds": item.future_seconds,
                "first_available": item.first_available.isoformat(),
            }
            for item in ranked
        ]
        return [item.professional_id for item in ranked]

    def register_contact(self, command: ContactRequest) -> dict[str, Any]:
        self._authorize(lock=True)
        if isinstance(self.identity, ContactPrincipal):
            raise SchedulingError("permission_denied")
        replay = self._replay("contact", command)
        if replay is not None:
            return replay
        phone_hash = digest(self.settings, f"contact:{self.tenant_id}", command.phone)
        contact = self.db.scalar(
            select(Contact).where(
                Contact.tenant_id == self.tenant_id, Contact.phone_hash == phone_hash
            )
        )
        if not contact:
            contact_id = uuid4()
            contact = Contact(
                id=contact_id,
                tenant_id=self.tenant_id,
                phone_hash=phone_hash,
                phone_ciphertext=seal(
                    self.settings, self.tenant_id, "contact", contact_id, "phone", command.phone
                ),
            )
            self.db.add(contact)
        elif not contact.active:
            raise SchedulingError("contact_unavailable")
        return self._save("contact", command, {"contact_id": str(contact.id)})

    def create_hold(self, command: HoldRequest) -> dict[str, Any]:
        now = self._authorize(lock=True)
        replay = self._replay("hold", command)
        if replay is not None:
            return replay
        self._contact(command.contact_id)
        service = self._service(command.service_id)
        resources = self._resources(service, command.unit_id, command.resource_ids)
        if command.reschedule_appointment_id is not None:
            old = self._appointment(
                AppointmentMutation(
                    idempotency_key=command.idempotency_key,
                    appointment_id=command.reschedule_appointment_id,
                    contact_id=command.contact_id,
                    version=command.appointment_version
                    if command.appointment_version is not None
                    else -1,
                ),
                now,
            )
            if (
                old.service_id != service.id
                or old.status not in ACTIVE_STATUSES
                or old.reschedule_count >= service.max_reschedules
                or now + timedelta(minutes=service.reschedule_notice_minutes) > old.starts_at
            ):
                raise SchedulingError("reschedule_policy")
        state = self._conversation(
            command.conversation_id, command.contact_id, command.conversation_version, "SELECT_TIME"
        )
        eligible = (
            [command.professional_id]
            if command.professional_id
            else self._rank_professionals(
                service,
                command.unit_id,
                command.starts_at,
                resources,
                now,
                command.reschedule_appointment_id,
            )
        )
        if not eligible:
            raise SchedulingError("slot_unavailable")
        professional_id = eligible[0]
        tenant = self.db.get(Tenant, self.tenant_id)
        day = command.starts_at.astimezone(ZoneInfo(tenant.timezone if tenant else "")).date()
        slots = self._slots(
            service,
            command.unit_id,
            professional_id,
            day,
            resources,
            now,
            exclude_appointment=command.reschedule_appointment_id,
        )
        slot = next((item for item in slots if item.start == command.starts_at), None)
        if slot is None:
            raise SchedulingError("slot_unavailable")
        hold = AppointmentHold(
            id=uuid4(),
            tenant_id=self.tenant_id,
            service_id=service.id,
            professional_id=professional_id,
            unit_id=command.unit_id,
            contact_id=command.contact_id,
            owner_user_id=self.identity.user_id,
            starts_at=slot.start,
            ends_at=slot.end,
            duration_minutes=self._duration(service, professional_id),
            buffer_before=service.buffer_before,
            buffer_after=service.buffer_after,
            occupied_start=slot.start - timedelta(minutes=service.buffer_before),
            occupied_end=slot.end + timedelta(minutes=service.buffer_after),
            state="held",
            expires_at=now + timedelta(minutes=service.hold_ttl_minutes),
            conversation_id=command.conversation_id,
            replaces_appointment_id=command.reschedule_appointment_id,
        )
        self.db.add(hold)
        self._flush()
        self.db.add_all(
            BookingResource(tenant_id=self.tenant_id, resource_id=resource_id, hold_id=hold.id)
            for resource_id in resources
        )
        if state:
            state.state, state.version, state.context = (
                "REVIEW",
                state.version + 1,
                {"hold_id": str(hold.id)},
            )
        self.db.add(
            AuditLog(
                tenant_id=self.tenant_id,
                actor_id=self.identity.user_id,
                action="hold.created",
                resource_id=hold.id,
            )
        )
        return self._save(
            "hold",
            command,
            {
                "hold_id": str(hold.id),
                "professional_id": str(professional_id),
                "expires_at": hold.expires_at.isoformat(),
                "state": "held",
                "strategy": "preferred" if command.professional_id else self.strategy.name,
                "selection_evidence": self.selection_evidence,
                "conversation_version": state.version if state else None,
            },
        )

    def _hold(self, hold_id: UUID, contact_id: UUID, now: datetime) -> AppointmentHold:
        hold = self.db.scalar(
            select(AppointmentHold)
            .where(
                AppointmentHold.tenant_id == self.tenant_id,
                AppointmentHold.id == hold_id,
                AppointmentHold.contact_id == contact_id,
                AppointmentHold.owner_user_id == self.identity.user_id,
            )
            .with_for_update()
        )
        if not hold or hold.state != "held" or hold.expires_at <= now:
            raise SchedulingError("hold_unavailable")
        self._duration(self._service(hold.service_id), hold.professional_id)
        self._contact(contact_id)
        return hold

    def _revalidate(
        self, hold: AppointmentHold, now: datetime, exclude_appointment: UUID | None = None
    ) -> None:
        service = self._service(hold.service_id)
        saved_resources = list(
            self.db.scalars(
                select(BookingResource.resource_id).where(
                    BookingResource.tenant_id == self.tenant_id, BookingResource.hold_id == hold.id
                )
            )
        )
        resources = self._resources(service, hold.unit_id, saved_resources)
        if set(resources) != set(saved_resources):
            raise SchedulingError("hold_stale")
        tenant = self.db.get(Tenant, self.tenant_id)
        day = hold.starts_at.astimezone(ZoneInfo(tenant.timezone if tenant else "")).date()
        slots = self._slots(
            service,
            hold.unit_id,
            hold.professional_id,
            day,
            resources,
            now,
            hold.id,
            exclude_appointment,
        )
        if (
            hold.buffer_before != service.buffer_before
            or hold.buffer_after != service.buffer_after
            or not any(item.start == hold.starts_at and item.end == hold.ends_at for item in slots)
        ):
            raise SchedulingError("hold_stale")

    def _new_patient(
        self, data: NewPatient, contact_id: UUID, service: Service, now: datetime
    ) -> Patient:
        if not data.purpose_acknowledged or (service.requires_birth_date and not data.birth_date):
            raise SchedulingError("patient_data_required")
        tenant = self.db.get(Tenant, self.tenant_id)
        if tenant is None:
            raise SchedulingError("permission_denied")
        validate_birth_date(data.birth_date, now, ZoneInfo(tenant.timezone))
        if data.birth_date and not service.requires_birth_date:
            raise SchedulingError("unnecessary_patient_data")
        patient_id = uuid4()
        patient = Patient(
            id=patient_id,
            tenant_id=self.tenant_id,
            name_ciphertext=seal(
                self.settings, self.tenant_id, "patient", patient_id, "name", data.display_name
            ),
            birth_date_ciphertext=seal(
                self.settings,
                self.tenant_id,
                "patient",
                patient_id,
                "birth_date",
                data.birth_date.isoformat(),
            )
            if data.birth_date
            else None,
        )
        self.db.add(patient)
        self._flush()
        self.db.add(
            ContactPatientLink(
                tenant_id=self.tenant_id,
                contact_id=contact_id,
                patient_id=patient_id,
                relationship="declared",
                revoked=False,
            )
        )
        return patient

    def _appointment_from_hold(
        self,
        hold: AppointmentHold,
        patient_id: UUID,
        appointment_id: UUID,
        reschedule_count: int = 0,
    ) -> Appointment:
        return Appointment(
            id=appointment_id,
            tenant_id=self.tenant_id,
            professional_id=hold.professional_id,
            service_id=hold.service_id,
            unit_id=hold.unit_id,
            contact_id=hold.contact_id,
            patient_id=patient_id,
            source_hold_id=hold.id,
            starts_at=hold.starts_at,
            ends_at=hold.ends_at,
            duration_minutes=hold.duration_minutes,
            buffer_before=hold.buffer_before,
            buffer_after=hold.buffer_after,
            occupied_start=hold.occupied_start,
            occupied_end=hold.occupied_end,
            status="scheduled",
            version=0,
            reschedule_count=reschedule_count,
        )

    def _record(
        self, appointment: Appointment, from_status: str | None, now: datetime, operation_key: str
    ) -> None:
        self.db.add(
            AppointmentTransition(
                tenant_id=self.tenant_id,
                appointment_id=appointment.id,
                from_status=from_status,
                to_status=appointment.status,
                actor_id=self.identity.user_id,
                created_at=now,
            )
        )
        self.db.add(
            AuditLog(
                tenant_id=self.tenant_id,
                actor_id=self.identity.user_id,
                action=f"appointment.{appointment.status}",
                resource_id=appointment.id,
            )
        )
        self.db.add(
            OutboxEvent(
                tenant_id=self.tenant_id,
                event_key=f"{operation_key}:{appointment.id}",
                event_type=f"appointment.{appointment.status}",
                aggregate_id=appointment.id,
                payload={"appointment_id": str(appointment.id), "version": appointment.version},
                created_at=now,
            )
        )

    def _transfer_resources(self, hold_id: UUID, appointment_id: UUID) -> None:
        for item in self.db.scalars(
            select(BookingResource).where(
                BookingResource.tenant_id == self.tenant_id, BookingResource.hold_id == hold_id
            )
        ):
            item.hold_id, item.appointment_id = None, appointment_id

    def _finish_conversation(
        self, hold: AppointmentHold, version: int | None, appointment_id: UUID
    ) -> None:
        state = self._conversation(
            hold.conversation_id, hold.contact_id, version, "REVIEW", hold.id
        )
        if state:
            state.state, state.version, state.context = (
                "DONE",
                state.version + 1,
                {"appointment_id": str(appointment_id)},
            )

    def confirm(self, command: ConfirmRequest) -> dict[str, Any]:
        now = self._authorize(lock=True)
        replay = self._replay("confirm", command)
        if replay is not None:
            return replay
        hold = self._hold(command.hold_id, command.contact_id, now)
        if hold.replaces_appointment_id is not None:
            raise SchedulingError("reschedule_required")
        self._revalidate(hold, now)
        # Validate conversation before creating anything; the final update is in this transaction.
        self._conversation(
            hold.conversation_id, hold.contact_id, command.conversation_version, "REVIEW", hold.id
        )
        if command.patient_id:
            patient = self._verified_patient(command.contact_id, command.patient_id, now)
        elif command.new_patient:
            patient = self._new_patient(
                command.new_patient, command.contact_id, self._service(hold.service_id), now
            )
        else:
            raise SchedulingError("patient_data_required")
        hold.state = "consumed"
        self._flush()
        appointment = self._appointment_from_hold(hold, patient.id, uuid4())
        self.db.add(appointment)
        self._flush()
        self._transfer_resources(hold.id, appointment.id)
        self._finish_conversation(hold, command.conversation_version, appointment.id)
        self._record(appointment, None, now, command.idempotency_key)
        return self._save(
            "confirm",
            command,
            {
                "appointment_id": str(appointment.id),
                "patient_id": str(patient.id),
                "status": appointment.status,
                "version": appointment.version,
            },
        )

    def _appointment(self, command: AppointmentMutation, now: datetime) -> Appointment:
        self._contact(command.contact_id)
        appointment = self.db.scalar(
            select(Appointment)
            .where(
                Appointment.tenant_id == self.tenant_id,
                Appointment.id == command.appointment_id,
                Appointment.contact_id == command.contact_id,
            )
            .with_for_update()
        )
        if (
            not appointment
            or appointment.version != command.version
            or not read_professional(self.db, self.identity, appointment.professional_id)
        ):
            raise SchedulingError("appointment_unavailable")
        try:
            self._verified_patient(command.contact_id, appointment.patient_id, now)
        except SchedulingError as error:
            raise SchedulingError("appointment_unavailable") from error
        return appointment

    def cancel(self, command: AppointmentMutation) -> dict[str, Any]:
        now = self._authorize(lock=True)
        replay = self._replay("cancel", command)
        if replay is not None:
            return replay
        appointment = self._appointment(command, now)
        service = self._service(appointment.service_id, require_active=False)
        validate_transition(appointment.status, "canceled", appointment.starts_at, now)
        if now + timedelta(minutes=service.cancellation_notice_minutes) > appointment.starts_at:
            raise SchedulingError("cancellation_policy")
        old_status = appointment.status
        appointment.status, appointment.version = "canceled", appointment.version + 1
        self._record(appointment, old_status, now, command.idempotency_key)
        return self._save(
            "cancel",
            command,
            {
                "appointment_id": str(appointment.id),
                "status": appointment.status,
                "version": appointment.version,
            },
        )

    def reschedule(self, command: RescheduleRequest) -> dict[str, Any]:
        now = self._authorize(lock=True)
        replay = self._replay("reschedule", command)
        if replay is not None:
            return replay
        old = self._appointment(command, now)
        service = self._service(old.service_id)
        validate_transition(old.status, "rescheduled", old.starts_at, now)
        if (
            now + timedelta(minutes=service.reschedule_notice_minutes) > old.starts_at
            or old.reschedule_count >= service.max_reschedules
        ):
            raise SchedulingError("reschedule_policy")
        hold = self._hold(command.hold_id, command.contact_id, now)
        if hold.service_id != old.service_id or hold.replaces_appointment_id != old.id:
            raise SchedulingError("service_mismatch")
        self._revalidate(hold, now, old.id)
        self._conversation(
            hold.conversation_id, hold.contact_id, command.conversation_version, "REVIEW", hold.id
        )
        new_id, old_status = uuid4(), old.status
        # The self-reference is deferred until commit; the old occupancy is released first.
        old.status, old.version, old.replaced_by_id = "rescheduled", old.version + 1, new_id
        hold.state = "consumed"
        self._flush()
        replacement = self._appointment_from_hold(
            hold, old.patient_id, new_id, old.reschedule_count + 1
        )
        self.db.add(replacement)
        self._flush()
        self._transfer_resources(hold.id, new_id)
        self._finish_conversation(hold, command.conversation_version, new_id)
        self._record(old, old_status, now, command.idempotency_key)
        self._record(replacement, None, now, command.idempotency_key)
        return self._save(
            "reschedule",
            command,
            {
                "previous_appointment_id": str(old.id),
                "appointment_id": str(new_id),
                "status": replacement.status,
                "version": 0,
            },
        )

    def transition(self, command: TransitionRequest) -> dict[str, Any]:
        now = self._authorize(lock=True)
        replay = self._replay("transition", command)
        if replay is not None:
            return replay
        appointment = self._appointment(command, now)
        validate_transition(appointment.status, command.target_status, appointment.starts_at, now)
        old_status = appointment.status
        appointment.status, appointment.version = command.target_status, appointment.version + 1
        self._record(appointment, old_status, now, command.idempotency_key)
        return self._save(
            "transition",
            command,
            {
                "appointment_id": str(appointment.id),
                "status": appointment.status,
                "version": appointment.version,
            },
        )

    def release_hold(self, command: ReleaseRequest) -> dict[str, Any]:
        now = self._authorize(lock=True)
        replay = self._replay("release", command)
        if replay is not None:
            return replay
        hold = self._hold(command.hold_id, command.contact_id, now)
        hold.state = "released"
        if hold.conversation_id:
            state = self.db.scalar(
                select(ConversationState)
                .where(
                    ConversationState.tenant_id == self.tenant_id,
                    ConversationState.conversation_id == hold.conversation_id,
                )
                .with_for_update()
            )
            if state and state.state == "REVIEW" and state.context.get("hold_id") == str(hold.id):
                state.state, state.version, state.context = "SELECT_TIME", state.version + 1, {}
        return self._save("release", command, {"hold_id": str(hold.id), "state": "released"})
