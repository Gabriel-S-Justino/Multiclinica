from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, update

from backend.application.pagination import cursor_for, offset_for
from backend.application.portal import read_professional, visible_professionals
from backend.application.portal_access import PortalContext, PortalError, command_values, now
from backend.application.portal_commands import (
    BlockDraft,
    ClinicPolicyDraft,
    ExceptionDraft,
    InvitationDraft,
    MembershipDraft,
    ProfessionalDraft,
    ResourceDraft,
    ScheduleDraft,
    ServiceDraft,
    UnitDraft,
    VerificationDraft,
    Versioned,
)
from backend.infrastructure.fields import seal
from backend.infrastructure.models import (
    Membership,
    PortalSession,
    Professional,
    ProfessionalAssignment,
    Resource,
    Tenant,
    Unit,
    User,
)
from backend.infrastructure.portal_models import (
    ClinicPolicy,
    Invitation,
    QueueMembership,
    ServiceQueue,
)
from backend.infrastructure.scheduling_models import (
    Appointment,
    BlockedPeriod,
    BookingResource,
    Contact,
    ContactPatientLink,
    Patient,
    ProfessionalSchedule,
    ProfessionalService,
    ScheduleException,
    Service,
    ServiceResource,
)
from backend.infrastructure.security import digest


class ClinicAdmin:
    def __init__(self, ctx: PortalContext) -> None:
        self.ctx, self.db = ctx, ctx.db

    def catalog(self) -> dict[str, Any]:
        self.ctx.validate(roles={"admin", "reception", "collaborator"})
        tenant = self.db.get(Tenant, self.ctx.tenant_id)
        services = list(
            self.db.scalars(
                select(Service)
                .where(Service.tenant_id == self.ctx.tenant_id)
                .order_by(Service.display_order, Service.id)
                .limit(100)
            )
        )
        units = self.db.scalars(
            select(Unit)
            .where(Unit.tenant_id == self.ctx.tenant_id, Unit.active.is_(True))
            .order_by(Unit.name)
            .limit(100)
        )
        resources = self.db.scalars(
            select(Resource)
            .where(Resource.tenant_id == self.ctx.tenant_id, Resource.active.is_(True))
            .order_by(Resource.name)
            .limit(100)
        )
        professionals = visible_professionals(self.db, self.ctx.identity)
        return {
            "timezone": tenant.timezone if tenant else "UTC",
            "services": [
                {
                    "id": str(item.id),
                    "name": item.name,
                    "active": item.active,
                    "policy_validated": item.policy_validated,
                    "duration_minutes": item.duration_minutes,
                    "requires_birth_date": item.requires_birth_date,
                    "requires_professional": item.requires_professional,
                    "bookable": bool(
                        item.active and item.policy_validated and item.requires_professional
                    ),
                }
                for item in services
            ],
            "units": [{"id": str(item.id), "name": item.name} for item in units],
            "resources": [
                {"id": str(item.id), "unit_id": str(item.unit_id), "name": item.name}
                for item in resources
            ],
            "professionals": [
                {"id": str(item.id), "display_name": item.display_name, "active": item.active}
                for item in professionals
            ],
        }

    def services(self) -> dict[str, Any]:
        self.ctx.admin()
        rows = self.db.scalars(
            select(Service)
            .where(Service.tenant_id == self.ctx.tenant_id)
            .order_by(Service.display_order, Service.id)
            .limit(100)
        )
        result = []
        for row in rows:
            data = {
                column.name: getattr(row, column.name)
                for column in Service.__table__.columns
                if column.name != "tenant_id"
            }
            data["id"], data["version"] = str(row.id), self.ctx.version("service", row.id)
            if not row.requires_professional:
                for key in (
                    "duration_minutes",
                    "step_minutes",
                    "buffer_before",
                    "buffer_after",
                    "min_notice_minutes",
                    "cancellation_notice_minutes",
                    "reschedule_notice_minutes",
                    "horizon_days",
                    "max_reschedules",
                    "hold_ttl_minutes",
                ):
                    data[key] = None
            data["required_resource_ids"] = [
                str(value)
                for value in self.db.scalars(
                    select(ServiceResource.resource_id).where(
                        ServiceResource.tenant_id == self.ctx.tenant_id,
                        ServiceResource.service_id == row.id,
                    )
                )
            ]
            result.append(data)
        return {"items": result}

    def save_service(self, command: ServiceDraft, entity_id: UUID | None = None) -> dict[str, Any]:
        self.ctx.admin(write=True)
        replay = self.ctx.replay("service.save", command, entity_id)
        if replay is not None:
            return replay
        values = command_values(command)
        values.pop("required_resource_ids")
        if command.service_queue_id:
            queue: ServiceQueue = self.ctx.entity(ServiceQueue, command.service_queue_id)
            if command.active and not queue.active:
                raise PortalError("queue_unavailable", 409)
        row: Service = (
            self.ctx.entity(Service, entity_id)
            if entity_id
            else Service(id=uuid4(), tenant_id=self.ctx.tenant_id, **values)
        )
        if entity_id:
            for key, value in values.items():
                setattr(row, key, value)
        else:
            self.db.add(row)
        version = self.ctx.bump("service", row.id, command.version)
        self.db.flush()
        for resource_id in set(command.required_resource_ids):
            resource: Resource = self.ctx.entity(Resource, resource_id)
            if not resource.active:
                raise PortalError("resource_unavailable", 409)
        self.db.execute(
            delete(ServiceResource).where(
                ServiceResource.tenant_id == self.ctx.tenant_id,
                ServiceResource.service_id == row.id,
            )
        )
        self.db.add_all(
            ServiceResource(
                tenant_id=self.ctx.tenant_id, service_id=row.id, resource_id=resource_id
            )
            for resource_id in set(command.required_resource_ids)
        )
        self.ctx.audit("service.saved", row.id)
        return self.ctx.save(
            "service.save", command, {"id": str(row.id), "version": version}, entity_id
        )

    def deactivate_service(self, command: Versioned, entity_id: UUID) -> dict[str, Any]:
        self.ctx.admin(write=True)
        replay = self.ctx.replay("service.deactivate", command, entity_id)
        if replay is not None:
            return replay
        row: Service = self.ctx.entity(Service, entity_id)
        version = self.ctx.bump("service", row.id, command.version)
        row.active = False
        self.ctx.audit("service.deactivated", row.id)
        return self.ctx.save(
            "service.deactivate",
            command,
            {"id": str(row.id), "version": version, "active": False},
            entity_id,
        )

    def professionals(self) -> dict[str, Any]:
        self.ctx.admin()
        rows = self.db.scalars(
            select(Professional)
            .where(Professional.tenant_id == self.ctx.tenant_id)
            .order_by(Professional.display_name)
            .limit(100)
        )
        return {
            "items": [
                {
                    "id": str(row.id),
                    "display_name": row.display_name,
                    "active": row.active,
                    "user_id": str(row.user_id) if row.user_id else None,
                    "version": self.ctx.version("professional", row.id),
                    "service_ids": [
                        str(value)
                        for value in self.db.scalars(
                            select(ProfessionalService.service_id).where(
                                ProfessionalService.tenant_id == self.ctx.tenant_id,
                                ProfessionalService.professional_id == row.id,
                                ProfessionalService.active.is_(True),
                            )
                        )
                    ],
                }
                for row in rows
            ]
        }

    def save_professional(
        self, command: ProfessionalDraft, entity_id: UUID | None = None
    ) -> dict[str, Any]:
        self.ctx.admin(write=True)
        replay = self.ctx.replay("professional.save", command, entity_id)
        if replay is not None:
            return replay
        if not command.display_name.strip():
            raise PortalError("validation_failed", 422)
        if command.user_id and not self.db.scalar(
            select(Membership.id).where(
                Membership.tenant_id == self.ctx.tenant_id,
                Membership.user_id == command.user_id,
                Membership.active.is_(True),
                Membership.role != "superadmin",
            )
        ):
            raise PortalError()
        for service_id in set(command.service_ids):
            self.ctx.entity(Service, service_id)
        row: Professional = (
            self.ctx.entity(Professional, entity_id)
            if entity_id
            else Professional(id=uuid4(), tenant_id=self.ctx.tenant_id)
        )
        row.display_name, row.active, row.user_id = (
            command.display_name.strip(),
            command.active,
            command.user_id,
        )
        self.db.add(row)
        version = self.ctx.bump("professional", row.id, command.version)
        self.db.flush()
        old = list(
            self.db.scalars(
                select(ProfessionalService).where(
                    ProfessionalService.tenant_id == self.ctx.tenant_id,
                    ProfessionalService.professional_id == row.id,
                )
            )
        )
        for link in old:
            link.active = link.service_id in command.service_ids
        known = {link.service_id for link in old}
        self.db.add_all(
            ProfessionalService(
                tenant_id=self.ctx.tenant_id, professional_id=row.id, service_id=value, active=True
            )
            for value in set(command.service_ids) - known
        )
        self.ctx.audit("professional.saved", row.id)
        return self.ctx.save(
            "professional.save", command, {"id": str(row.id), "version": version}, entity_id
        )

    def team(self, limit: int, cursor: str | None) -> dict[str, Any]:
        self.ctx.admin()
        filters = {"limit": limit}
        offset = offset_for(self.ctx, cursor, "clinic-memberships", filters)
        items = self.memberships(limit=limit + 1, offset=offset)
        return {
            "items": items[:limit],
            "next_cursor": cursor_for(
                self.ctx,
                offset + limit if len(items) > limit else None,
                "clinic-memberships",
                filters,
            ),
        }

    def memberships(self, *, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        members = self.db.execute(
            select(Membership, User)
            .join(User, User.id == Membership.user_id)
            .where(
                Membership.tenant_id == self.ctx.tenant_id,
                Membership.role.in_(("admin", "reception", "collaborator")),
                User.is_service.is_(False),
                User.deleted_at.is_(None),
                Membership.deleted_at.is_(None),
            )
            .order_by(User.login)
            .offset(offset)
            .limit(limit)
        )
        return [
            {
                "id": str(member.id),
                "user_id": str(user.id),
                "login": user.login,
                "role": member.role,
                "active": member.active,
                "can_manage_schedule": member.can_manage_schedule,
                "version": self.ctx.version("membership", member.id),
                "professional_ids": [
                    str(value)
                    for value in self.db.scalars(
                        select(ProfessionalAssignment.professional_id).where(
                            ProfessionalAssignment.tenant_id == self.ctx.tenant_id,
                            ProfessionalAssignment.membership_id == member.id,
                        )
                    )
                ],
                "queue_ids": [
                    str(value)
                    for value in self.db.scalars(
                        select(QueueMembership.queue_id).where(
                            QueueMembership.tenant_id == self.ctx.tenant_id,
                            QueueMembership.membership_id == member.id,
                        )
                    )
                ],
            }
            for member, user in members
        ]

    def save_membership(self, command: MembershipDraft, entity_id: UUID) -> dict[str, Any]:
        self.ctx.admin(write=True)
        return self.update_permissions(command, entity_id)

    def remove_membership(self, command: Versioned, entity_id: UUID) -> dict[str, Any]:
        self.ctx.admin(write=True)
        replay = self.ctx.replay("membership.delete", command, entity_id)
        if replay is not None:
            return replay
        row: Membership = self.ctx.entity(Membership, entity_id)
        if row.role not in {"admin", "reception", "collaborator"}:
            raise PortalError("permission_denied", 403)
        self.update_permissions(
            MembershipDraft(
                idempotency_key=command.idempotency_key,
                version=command.version,
                role=row.role,
                active=False,
                can_manage_schedule=False,
                professional_ids=[],
                queue_ids=[],
            ),
            entity_id,
            deleting=True,
        )
        return self.ctx.save("membership.delete", command, {"id": str(entity_id)}, entity_id)

    def update_permissions(
        self, command: MembershipDraft, entity_id: UUID, *, deleting: bool = False
    ) -> dict[str, Any]:
        replay = None if deleting else self.ctx.replay("membership.save", command, entity_id)
        if replay is not None:
            return replay
        row: Membership = self.ctx.entity(Membership, entity_id)
        user = self.db.get(User, row.user_id)
        if row.deleted_at is not None or not user or user.deleted_at is not None:
            raise PortalError()
        if row.role not in {"admin", "reception", "collaborator"} or user.is_service:
            raise PortalError("permission_denied", 403)
        if row.active and row.role == "admin" and (not command.active or command.role != "admin"):
            others = self.db.scalar(
                select(func.count())
                .select_from(Membership)
                .join(User, User.id == Membership.user_id)
                .where(
                    Membership.tenant_id == self.ctx.tenant_id,
                    Membership.role == "admin",
                    Membership.active.is_(True),
                    Membership.id != row.id,
                    User.active.is_(True),
                    User.is_service.is_(False),
                )
            )
            if not others:
                raise PortalError("last_administrator", 409)
        for value in set(command.professional_ids):
            self.ctx.entity(Professional, value)
        for value in set(command.queue_ids):
            self.ctx.entity(ServiceQueue, value)
        version = self.ctx.bump("membership", row.id, command.version)
        row.role, row.active, row.can_manage_schedule = (
            command.role,
            command.active,
            command.can_manage_schedule,
        )
        self.db.execute(
            delete(ProfessionalAssignment).where(
                ProfessionalAssignment.tenant_id == self.ctx.tenant_id,
                ProfessionalAssignment.membership_id == row.id,
            )
        )
        self.db.execute(
            delete(QueueMembership).where(
                QueueMembership.tenant_id == self.ctx.tenant_id,
                QueueMembership.membership_id == row.id,
            )
        )
        self.db.add_all(
            ProfessionalAssignment(
                tenant_id=self.ctx.tenant_id, membership_id=row.id, professional_id=value
            )
            for value in set(command.professional_ids)
        )
        self.db.add_all(
            QueueMembership(tenant_id=self.ctx.tenant_id, membership_id=row.id, queue_id=value)
            for value in set(command.queue_ids)
        )
        self.db.execute(delete(PortalSession).where(PortalSession.membership_id == row.id))
        if deleting:
            row.deleted_at = now(self.db)
            self.db.execute(
                update(Invitation)
                .where(
                    Invitation.tenant_id == self.ctx.tenant_id,
                    Invitation.recipient_hash
                    == digest(self.ctx.settings, "invite-recipient", user.login.lower()),
                    Invitation.status == "pending",
                )
                .values(status="revoked")
            )
            self.ctx.audit("membership.deleted", row.id)
            return {"id": str(row.id), "version": version}
        self.ctx.audit("membership.permissions_changed", row.id)
        return self.ctx.save(
            "membership.save", command, {"id": str(row.id), "version": version}, entity_id
        )

    def invite(self, command: InvitationDraft) -> dict[str, Any]:
        moment = self.ctx.admin(write=True)
        replay = self.ctx.replay("invitation.create", command)
        if replay is not None:
            return replay
        login = command.login.strip().lower()
        invitation_id = uuid4()
        row = Invitation(
            id=invitation_id,
            tenant_id=self.ctx.tenant_id,
            recipient_hash=digest(self.ctx.settings, "invite-recipient", login),
            login_ciphertext=seal(
                self.ctx.settings, self.ctx.tenant_id, "invitation", invitation_id, "login", login
            ),
            role=command.role,
            created_at=moment,
            expires_at=moment + timedelta(days=7),
        )
        self.db.add(row)
        self.ctx.audit("invitation.requested", row.id)
        # Same receipt whether a global account exists; no email service is implied.
        return self.ctx.save(
            "invitation.create",
            command,
            {"id": str(row.id), "status": "pending", "delivery": "operator"},
        )

    def _schedule_access(self, professional_id: UUID, *, write: bool = False) -> None:
        self.ctx.validate(lock=write, roles={"admin", "reception", "collaborator"})
        member = self.db.get(Membership, self.ctx.identity.membership_id)
        if not read_professional(self.db, self.ctx.identity, professional_id):
            raise PortalError()
        if (
            write
            and self.ctx.identity.role != "admin"
            and (not member or not member.can_manage_schedule)
        ):
            raise PortalError("permission_denied", 403)

    def schedules(self, professional_id: UUID) -> dict[str, Any]:
        self._schedule_access(professional_id)

        def rows(model: Any, kind: str) -> list[dict[str, Any]]:
            items = self.db.scalars(
                select(model)
                .where(
                    model.tenant_id == self.ctx.tenant_id, model.professional_id == professional_id
                )
                .order_by(model.id)
                .limit(100)
            )
            result = []
            for item in items:
                data = {
                    column.name: getattr(item, column.name)
                    for column in model.__table__.columns
                    if column.name != "tenant_id"
                }
                data["version"] = self.ctx.version(kind, item.id)
                result.append(data)
            return result

        return {
            "schedules": rows(ProfessionalSchedule, "schedule"),
            "exceptions": rows(ScheduleException, "exception"),
            "blocks": rows(BlockedPeriod, "block"),
        }

    def save_schedule(
        self,
        command: ScheduleDraft | ExceptionDraft | BlockDraft,
        kind: str,
        entity_id: UUID | None = None,
    ) -> dict[str, Any]:
        self._schedule_access(command.professional_id, write=True)
        self.ctx.entity(Unit, command.unit_id)
        replay = self.ctx.replay(f"{kind}.save", command, entity_id)
        if replay is not None:
            return replay
        models = {
            "schedule": ProfessionalSchedule,
            "exception": ScheduleException,
            "block": BlockedPeriod,
        }
        model = models[kind]
        row: Any = (
            self.ctx.entity(model, entity_id)
            if entity_id
            else model(id=uuid4(), tenant_id=self.ctx.tenant_id, **command_values(command))
        )
        if entity_id:
            self._schedule_access(row.professional_id, write=True)
            for key, value in command_values(command).items():
                setattr(row, key, value)
        self.db.add(row)
        version = self.ctx.bump(kind, row.id, command.version)
        self.ctx.audit(f"{kind}.saved", row.id)
        return self.ctx.save(
            f"{kind}.save", command, {"id": str(row.id), "version": version}, entity_id
        )

    def delete_schedule(self, command: Versioned, kind: str, entity_id: UUID) -> dict[str, Any]:
        self.ctx.validate(lock=True, roles={"admin", "reception", "collaborator"})
        replay = self.ctx.replay(f"{kind}.delete", command, entity_id)
        if replay is not None:
            return replay
        models = {
            "schedule": ProfessionalSchedule,
            "exception": ScheduleException,
            "block": BlockedPeriod,
        }
        row = self.ctx.entity(models[kind], entity_id)
        self._schedule_access(row.professional_id, write=True)
        version = self.ctx.bump(kind, row.id, command.version)
        self.db.delete(row)
        self.ctx.audit(f"{kind}.deleted", entity_id)
        return self.ctx.save(
            f"{kind}.delete", command, {"id": str(entity_id), "version": version}, entity_id
        )

    def units(self) -> dict[str, Any]:
        self.ctx.admin()
        units = self.db.scalars(
            select(Unit).where(Unit.tenant_id == self.ctx.tenant_id).order_by(Unit.name).limit(100)
        )
        resources = self.db.scalars(
            select(Resource)
            .where(Resource.tenant_id == self.ctx.tenant_id)
            .order_by(Resource.name)
            .limit(100)
        )
        return {
            "units": [
                {
                    "id": str(item.id),
                    "name": item.name,
                    "active": item.active,
                    "version": self.ctx.version("unit", item.id),
                }
                for item in units
            ],
            "resources": [
                {
                    "id": str(item.id),
                    "unit_id": str(item.unit_id),
                    "name": item.name,
                    "active": item.active,
                    "version": self.ctx.version("resource", item.id),
                }
                for item in resources
            ],
        }

    def save_unit(
        self, command: UnitDraft | ResourceDraft, entity_id: UUID | None = None
    ) -> dict[str, Any]:
        self.ctx.admin(write=True)
        resource = isinstance(command, ResourceDraft)
        kind, model = ("resource", Resource) if resource else ("unit", Unit)
        replay = self.ctx.replay(f"{kind}.save", command, entity_id)
        if replay is not None:
            return replay
        values = command_values(command)
        if not command.name.strip():
            raise PortalError("validation_failed", 422)
        if resource:
            self.ctx.entity(Unit, values["unit_id"])
        row: Any = (
            self.ctx.entity(model, entity_id)
            if entity_id
            else model(id=uuid4(), tenant_id=self.ctx.tenant_id, **values)
        )
        if entity_id:
            if (
                resource
                and row.unit_id != values["unit_id"]
                and self.db.scalar(
                    select(BookingResource.id)
                    .where(
                        BookingResource.tenant_id == self.ctx.tenant_id,
                        BookingResource.resource_id == row.id,
                    )
                    .limit(1)
                )
            ):
                raise PortalError("resource_in_use", 409)
            for key, value in values.items():
                setattr(row, key, value)
        self.db.add(row)
        version = self.ctx.bump(kind, row.id, command.version)
        self.ctx.audit(f"{kind}.saved", row.id)
        return self.ctx.save(
            f"{kind}.save", command, {"id": str(row.id), "version": version}, entity_id
        )

    def policy(self) -> dict[str, Any]:
        self.ctx.admin()
        row = self.db.scalar(
            select(ClinicPolicy).where(ClinicPolicy.tenant_id == self.ctx.tenant_id)
        )
        return {
            "policy": {
                "identity_policy_approved": row.identity_policy_approved,
                "identity_policy_reference": row.identity_policy_reference,
                "verification_ttl_minutes": row.verification_ttl_minutes,
                "version": row.version,
            }
            if row
            else None
        }

    def save_policy(self, command: ClinicPolicyDraft) -> dict[str, Any]:
        self.ctx.admin(write=True)
        replay = self.ctx.replay("policy.save", command)
        if replay is not None:
            return replay
        row = self.db.scalar(
            select(ClinicPolicy)
            .where(ClinicPolicy.tenant_id == self.ctx.tenant_id)
            .with_for_update()
        )
        if command.version != (row.version if row else 0):
            raise PortalError("version_conflict", 409)
        if row is None:
            row = ClinicPolicy(id=uuid4(), tenant_id=self.ctx.tenant_id, **command_values(command))
            self.db.add(row)
        else:
            for key, value in command_values(command).items():
                setattr(row, key, value)
        row.version = command.version + 1
        self.ctx.audit("identity_policy.saved", row.id)
        return self.ctx.save("policy.save", command, {"version": row.version})

    def verify_patient(self, command: VerificationDraft) -> dict[str, Any]:
        moment = self.ctx.validate(lock=True, roles={"admin", "reception"}, recent=True)
        replay = self.ctx.replay("patient.verify", command)
        if replay is not None:
            return replay
        self.ctx.entity(Contact, command.contact_id)
        self.ctx.entity(Patient, command.patient_id)
        policy = self.db.scalar(
            select(ClinicPolicy).where(
                ClinicPolicy.tenant_id == self.ctx.tenant_id,
                ClinicPolicy.identity_policy_approved.is_(True),
            )
        )
        if policy is None:
            raise PortalError("identity_policy_required", 409)
        if self.ctx.identity.role == "reception":
            visible = [item.id for item in visible_professionals(self.db, self.ctx.identity)]
            if not self.db.scalar(
                select(Appointment.id)
                .where(
                    Appointment.tenant_id == self.ctx.tenant_id,
                    Appointment.contact_id == command.contact_id,
                    Appointment.patient_id == command.patient_id,
                    Appointment.professional_id.in_(visible),
                )
                .limit(1)
            ):
                raise PortalError()
        row = self.db.scalar(
            select(ContactPatientLink).where(
                ContactPatientLink.tenant_id == self.ctx.tenant_id,
                ContactPatientLink.contact_id == command.contact_id,
                ContactPatientLink.patient_id == command.patient_id,
            )
        )
        if row is None:
            row = ContactPatientLink(
                tenant_id=self.ctx.tenant_id,
                contact_id=command.contact_id,
                patient_id=command.patient_id,
                relationship=command.relationship,
            )
            self.db.add(row)
        row.relationship, row.verification_method = command.relationship, "manual_clinic"
        row.verified_at, row.verified_until = (
            moment,
            moment + timedelta(minutes=policy.verification_ttl_minutes),
        )
        row.verified_by, row.verification_reference, row.revoked = (
            self.ctx.identity.user_id,
            command.evidence_reference,
            False,
        )
        self.db.flush()
        self.ctx.audit("patient.link_verified", row.id)
        return self.ctx.save(
            "patient.verify",
            command,
            {"verified": True, "verified_until": row.verified_until.isoformat()},
        )
