from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import and_, select

from backend.application.pagination import cursor_for, offset_for
from backend.application.portal import visible_professionals
from backend.application.portal_access import PortalContext, PortalError, now
from backend.application.scheduling import Scheduler
from backend.application.scheduling_commands import AvailabilityQuery
from backend.domain.scheduling import ACTIVE_STATUSES
from backend.infrastructure.fields import unseal
from backend.infrastructure.models import AuditLog, Professional, Tenant, Unit
from backend.infrastructure.portal_models import AdminNotification
from backend.infrastructure.scheduling_models import (
    Appointment,
    AppointmentHold,
    Contact,
    ContactPatientLink,
    Patient,
    Service,
)


class PortalRead:
    def __init__(self, ctx: PortalContext) -> None:
        self.ctx, self.db = ctx, ctx.db

    def visible_ids(self) -> list[UUID]:
        return [item.id for item in visible_professionals(self.db, self.ctx.identity)]

    def appointment(self, appointment_id: UUID) -> Appointment:
        self.ctx.validate(roles={"admin", "reception", "collaborator"})
        row = self.db.scalar(
            select(Appointment).where(
                Appointment.tenant_id == self.ctx.tenant_id,
                Appointment.id == appointment_id,
                Appointment.professional_id.in_(self.visible_ids()),
            )
        )
        if row is None:
            raise PortalError()
        return row

    def describe(self, row: Appointment, *, exceptional: bool = False) -> dict[str, Any]:
        # Called only after normal resource authorization or validation of a break-glass grant.
        tenant = self.db.get(Tenant, row.tenant_id)
        zone = ZoneInfo(tenant.timezone if tenant else "UTC")
        patient = self.db.scalar(
            select(Patient).where(Patient.tenant_id == row.tenant_id, Patient.id == row.patient_id)
        )
        service = self.db.scalar(
            select(Service).where(Service.tenant_id == row.tenant_id, Service.id == row.service_id)
        )
        professional = self.db.scalar(
            select(Professional).where(
                Professional.tenant_id == row.tenant_id, Professional.id == row.professional_id
            )
        )
        unit = self.db.scalar(
            select(Unit).where(Unit.tenant_id == row.tenant_id, Unit.id == row.unit_id)
        )
        moment = now(self.db)
        verified = (
            self.db.scalar(
                select(ContactPatientLink.id).where(
                    ContactPatientLink.tenant_id == row.tenant_id,
                    ContactPatientLink.contact_id == row.contact_id,
                    ContactPatientLink.patient_id == row.patient_id,
                    ContactPatientLink.verification_method == "manual_clinic",
                    ContactPatientLink.verified_by.is_not(None),
                    ContactPatientLink.verified_at <= moment,
                    ContactPatientLink.verified_until > moment,
                    ContactPatientLink.revoked.is_(False),
                )
            )
            is not None
        )
        actions = []
        if not exceptional:
            if not verified and self.ctx.identity.role in {"admin", "reception"}:
                actions.append("verify_identity")
            if verified and row.status in ACTIVE_STATUSES:
                if (
                    service
                    and service.policy_validated
                    and moment + timedelta(minutes=service.cancellation_notice_minutes)
                    <= row.starts_at
                ):
                    actions.append("cancel")
                if (
                    service
                    and service.active
                    and service.policy_validated
                    and row.reschedule_count < service.max_reschedules
                    and moment + timedelta(minutes=service.reschedule_notice_minutes)
                    <= row.starts_at
                ):
                    actions.append("reschedule")
                if row.status == "scheduled":
                    actions.append("confirm")
                if moment >= row.starts_at:
                    actions.extend(["complete", "no_show"])
        return {
            "id": str(row.id),
            "status": row.status,
            "version": row.version,
            "patient_id": str(row.patient_id),
            "contact_id": str(row.contact_id),
            "patient_name": unseal(
                self.ctx.settings,
                row.tenant_id,
                "patient",
                patient.id,
                "name",
                patient.name_ciphertext,
            )
            if patient
            else None,
            "service_id": str(row.service_id),
            "service_name": service.name if service else None,
            "professional_id": str(row.professional_id),
            "professional_name": professional.display_name if professional else None,
            "unit_id": str(row.unit_id),
            "unit_name": unit.name if unit else None,
            "starts_at": row.starts_at.isoformat(),
            "ends_at": row.ends_at.isoformat(),
            "duration_minutes": row.duration_minutes,
            "timezone": str(zone),
            "local_date": row.starts_at.astimezone(zone).date().isoformat(),
            "local_start": row.starts_at.astimezone(zone).strftime("%H:%M"),
            "local_end": row.ends_at.astimezone(zone).strftime("%H:%M"),
            "identity_verified": verified,
            "actions": actions,
        }

    def appointments(
        self, first: date, last: date, professional_id: UUID | None, limit: int, cursor: str | None
    ) -> dict[str, Any]:
        self.ctx.validate(roles={"admin", "reception", "collaborator"})
        if not 0 <= (last - first).days < 31:
            raise PortalError("invalid_period", 422)
        tenant = self.db.get(Tenant, self.ctx.tenant_id)
        zone = ZoneInfo(tenant.timezone if tenant else "UTC")
        start = datetime.combine(first, datetime.min.time(), zone)
        end = datetime.combine(last + timedelta(days=1), datetime.min.time(), zone)
        visible = self.visible_ids()
        if professional_id and professional_id not in visible:
            raise PortalError()
        filters = {
            "first": first.isoformat(),
            "last": last.isoformat(),
            "professional": str(professional_id) if professional_id else None,
            "limit": limit,
        }
        offset = offset_for(self.ctx, cursor, "appointments", filters)
        query = select(Appointment).where(
            Appointment.tenant_id == self.ctx.tenant_id,
            Appointment.professional_id.in_([professional_id] if professional_id else visible),
            Appointment.starts_at < end,
            Appointment.ends_at > start,
        )
        rows = list(
            self.db.scalars(
                query.order_by(Appointment.starts_at, Appointment.id)
                .offset(offset)
                .limit(limit + 1)
            )
        )
        return {
            "items": [self.describe(row) for row in rows[:limit]],
            "timezone": str(zone),
            "next_cursor": cursor_for(
                self.ctx, offset + limit if len(rows) > limit else None, "appointments", filters
            ),
        }

    def availability(self, command: AvailabilityQuery, cursor: str | None) -> dict[str, Any]:
        self.ctx.validate(roles={"admin", "reception", "collaborator"})
        filters = command.model_dump(mode="json", exclude={"offset"})
        offset = offset_for(self.ctx, cursor, "availability", filters)
        page = Scheduler(self.db, self.ctx.settings, self.ctx.identity).availability(
            command.model_copy(update={"offset": offset})
        )
        tenant = self.db.get(Tenant, self.ctx.tenant_id)
        zone = ZoneInfo(tenant.timezone if tenant else "UTC")
        return {
            "items": [
                {
                    "professional_id": str(item.professional_id),
                    "starts_at": item.start.isoformat(),
                    "ends_at": item.end.isoformat(),
                    "local_date": item.start.astimezone(zone).date().isoformat(),
                    "local_start": item.start.astimezone(zone).strftime("%H:%M"),
                    "local_end": item.end.astimezone(zone).strftime("%H:%M"),
                }
                for item in page.items
            ],
            "timezone": str(zone),
            "next_cursor": cursor_for(self.ctx, page.next_offset, "availability", filters),
        }

    def hold_summary(self, hold_id: UUID) -> dict[str, Any]:
        moment = self.ctx.validate(roles={"admin", "reception", "collaborator"})
        hold = self.db.scalar(
            select(AppointmentHold).where(
                AppointmentHold.tenant_id == self.ctx.tenant_id,
                AppointmentHold.id == hold_id,
                AppointmentHold.owner_user_id == self.ctx.identity.user_id,
                AppointmentHold.state == "held",
                AppointmentHold.expires_at > moment,
            )
        )
        if hold is None or hold.professional_id not in self.visible_ids():
            raise PortalError()
        service: Service = self.ctx.entity(Service, hold.service_id)
        professional: Professional = self.ctx.entity(Professional, hold.professional_id)
        unit: Unit = self.ctx.entity(Unit, hold.unit_id)
        tenant = self.db.get(Tenant, self.ctx.tenant_id)
        zone = ZoneInfo(tenant.timezone if tenant else "UTC")
        return {
            "hold_id": str(hold.id),
            "service_name": service.name,
            "professional_name": professional.display_name,
            "unit_name": unit.name,
            "duration_minutes": hold.duration_minutes,
            "starts_at": hold.starts_at.isoformat(),
            "local_date": hold.starts_at.astimezone(zone).date().isoformat(),
            "local_start": hold.starts_at.astimezone(zone).strftime("%H:%M"),
            "expires_at": hold.expires_at.isoformat(),
            "timezone": str(zone),
        }

    def patients(self, contact_id: UUID) -> dict[str, Any]:
        self.ctx.validate(roles={"admin", "reception", "collaborator"})
        self.ctx.entity(Contact, contact_id)
        pairs = self.db.execute(
            select(ContactPatientLink, Patient)
            .join(
                Patient,
                and_(
                    Patient.tenant_id == ContactPatientLink.tenant_id,
                    Patient.id == ContactPatientLink.patient_id,
                ),
            )
            .where(
                ContactPatientLink.tenant_id == self.ctx.tenant_id,
                ContactPatientLink.contact_id == contact_id,
            )
            .limit(100)
        )
        moment, result = now(self.db), []
        for link, patient in pairs:
            if self.ctx.identity.role != "admin" and not self.db.scalar(
                select(Appointment.id)
                .where(
                    Appointment.tenant_id == self.ctx.tenant_id,
                    Appointment.patient_id == patient.id,
                    Appointment.contact_id == contact_id,
                    Appointment.professional_id.in_(self.visible_ids()),
                )
                .limit(1)
            ):
                continue
            verified = bool(
                not link.revoked
                and link.verification_method == "manual_clinic"
                and link.verified_by
                and link.verified_at
                and link.verified_until
                and link.verified_at <= moment < link.verified_until
            )
            result.append(
                {
                    "id": str(patient.id),
                    "display_name": unseal(
                        self.ctx.settings,
                        self.ctx.tenant_id,
                        "patient",
                        patient.id,
                        "name",
                        patient.name_ciphertext,
                    ),
                    "verified": verified,
                    "relationship": link.relationship,
                }
            )
        return {"items": result}

    def audit(self, limit: int, cursor: str | None) -> dict[str, Any]:
        self.ctx.validate(roles={"admin"})
        if not self.ctx.identity.mfa_verified:
            raise PortalError("permission_denied", 403)
        filters = {"limit": limit}
        offset = offset_for(self.ctx, cursor, "audit", filters)
        rows = list(
            self.db.scalars(
                select(AuditLog)
                .where(AuditLog.tenant_id == self.ctx.tenant_id)
                .order_by(AuditLog.created_at.desc(), AuditLog.id)
                .offset(offset)
                .limit(limit + 1)
            )
        )
        return {
            "items": [
                {
                    "id": str(row.id),
                    "action": row.action,
                    "resource_id": str(row.resource_id) if row.resource_id else None,
                    "created_at": row.created_at.isoformat(),
                    "correlation_id": str(row.correlation_id),
                }
                for row in rows[:limit]
            ],
            "next_cursor": cursor_for(
                self.ctx, offset + limit if len(rows) > limit else None, "audit", filters
            ),
        }

    def notifications(self) -> dict[str, Any]:
        self.ctx.admin()
        rows = self.db.scalars(
            select(AdminNotification)
            .where(AdminNotification.tenant_id == self.ctx.tenant_id)
            .order_by(AdminNotification.created_at.desc())
            .limit(50)
        )
        return {
            "items": [
                {
                    "id": str(row.id),
                    "type": row.notification_type,
                    "resource_id": str(row.resource_id),
                    "created_at": row.created_at.isoformat(),
                }
                for row in rows
            ]
        }
