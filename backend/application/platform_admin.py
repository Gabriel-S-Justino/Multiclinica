from datetime import date, datetime, time, timedelta
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, literal, select, text, union_all
from sqlalchemy.orm import aliased

from backend.application.auth import revoke_user_sessions
from backend.application.clinic_admin import ClinicAdmin
from backend.application.invitations import platform_activation_code
from backend.application.pagination import cursor_for, offset_for
from backend.application.portal_access import PortalContext, PortalError, now
from backend.application.portal_commands import (
    BreakGlassDecision,
    InvitationDraft,
    MembershipDraft,
    PlatformInvitationDraft,
    PlatformUserStatus,
    TenantDraft,
    Versioned,
)
from backend.application.scheduling_commands import Mutation
from backend.infrastructure.db import set_tenant
from backend.infrastructure.fields import seal, unseal
from backend.infrastructure.models import (
    AuditLog,
    Membership,
    PortalSession,
    Professional,
    Tenant,
    User,
    UserProfile,
)
from backend.infrastructure.portal_models import (
    AdminNotification,
    BreakGlassRequest,
    Invitation,
    PlatformAudit,
    PlatformInvitation,
    PlatformOperator,
    ServiceQueue,
)
from backend.infrastructure.scheduling_models import Appointment
from backend.infrastructure.security import digest


class PlatformAdmin:
    def __init__(self, ctx: PortalContext) -> None:
        self.ctx, self.db = ctx, ctx.db

    def operator(self, *, write: bool = False) -> None:
        operator = self.db.get(PlatformOperator, self.ctx.identity.user_id)
        identity = self.ctx.identity
        if (
            not operator
            or not operator.active
            or not self.ctx.global_operation
            or not identity.mfa_verified
        ):
            raise PortalError("permission_denied", 403)
        self.db.execute(text("SELECT set_config('app.platform', 'true', true)"))
        if write:
            if identity.authenticated_at is None or now(
                self.db
            ) - identity.authenticated_at > timedelta(minutes=15):
                raise PortalError("reauthentication_required", 403)
            self.db.execute(text("SELECT pg_advisory_xact_lock(128019, 1)"))

    def audit(self, tenant_id: UUID | None, action: str, resource_id: UUID | None) -> None:
        self.db.add(
            PlatformAudit(
                actor_id=self.ctx.identity.user_id,
                tenant_id=tenant_id,
                action=action,
                resource_id=resource_id,
                correlation_id=self.ctx.correlation_id,
                created_at=now(self.db),
            )
        )

    def tenants(self, limit: int, cursor: str | None) -> dict[str, Any]:
        self.operator()
        filters = {"limit": limit}
        offset = offset_for(self.ctx, cursor, "platform-tenants", filters)
        rows = list(
            self.db.scalars(
                select(Tenant)
                .where(Tenant.deleted_at.is_(None), Tenant.internal.is_(False))
                .order_by(Tenant.name, Tenant.id)
                .offset(offset)
                .limit(limit + 1)
            )
        )
        return {
            "items": [
                {
                    "id": str(row.id),
                    "name": row.name,
                    "timezone": row.timezone,
                    "active": row.active,
                    "version": row.version,
                    "registration": row.registration,
                }
                for row in rows[:limit]
            ],
            "next_cursor": cursor_for(
                self.ctx, offset + limit if len(rows) > limit else None, "platform-tenants", filters
            ),
        }

    def save_tenant(self, command: TenantDraft, tenant_id: UUID | None = None) -> dict[str, Any]:
        self.operator(write=True)
        replay = self.ctx.replay("tenant.save", command, tenant_id)
        if replay is not None:
            return replay
        row = (
            self.db.get(Tenant, tenant_id, with_for_update=True)
            if tenant_id
            else Tenant(id=uuid4())
        )
        if row is None or row.deleted_at is not None or row.internal:
            raise PortalError()
        if command.version != (row.version if tenant_id else 0):
            raise PortalError("version_conflict", 409)
        row.name, row.timezone, row.active, row.version = (
            command.name.strip(),
            command.timezone,
            command.active,
            command.version + 1,
        )
        if not row.name:
            raise PortalError("validation_failed", 422)
        if tenant_id is None and command.registration is None:
            raise PortalError("clinic_registration_required", 422)
        if command.registration is not None:
            row.registration = command.registration.model_dump()
        self.db.add(row)
        self.audit(row.id, "tenant.saved", row.id)
        return self.ctx.save(
            "tenant.save", command, {"id": str(row.id), "version": row.version}, tenant_id
        )

    def invite_administrator(self, command: InvitationDraft, tenant_id: UUID) -> dict[str, Any]:
        if command.role != "admin":
            raise PortalError("validation_failed", 422)
        return self.invite_user(command, tenant_id)

    def invite_superadmin(self, command: PlatformInvitationDraft) -> dict[str, Any]:
        self.operator(write=True)
        replay = self.ctx.replay("platform.operator_invite", command)
        if replay is None:
            login = command.login.lower()
            if self.db.scalar(select(User.id).where(User.login == login)) is not None:
                raise PortalError("platform_login_exists", 409)
            invitation_id = uuid4()
            code = platform_activation_code(self.ctx.settings, invitation_id)
            expires_at = now(self.db) + timedelta(days=1)
            self.db.add(
                PlatformInvitation(
                    id=invitation_id,
                    issuer_id=self.ctx.identity.user_id,
                    recipient_hash=digest(self.ctx.settings, "invite-recipient", login),
                    proof_hash=digest(self.ctx.settings, "platform-invitation-proof", code),
                    expires_at=expires_at,
                )
            )
            self.audit(None, "platform_operator.invited", invitation_id)
            replay = self.ctx.save(
                "platform.operator_invite",
                command,
                {"id": str(invitation_id), "expires_at": expires_at.isoformat()},
            )
        return {
            **replay,
            "activation_code": platform_activation_code(self.ctx.settings, UUID(replay["id"])),
        }

    def invite_user(self, command: InvitationDraft, tenant_id: UUID) -> dict[str, Any]:
        self.operator(write=True)
        replay = self.ctx.replay("tenant.admin_invite", command, tenant_id)
        if replay is not None:
            return replay
        tenant = self.db.get(Tenant, tenant_id)
        if not tenant or not tenant.active or tenant.deleted_at is not None or tenant.internal:
            raise PortalError()
        moment, invitation_id = now(self.db), uuid4()
        login = command.login.strip().lower()
        set_tenant(self.db, tenant_id)
        self.db.add(
            Invitation(
                id=invitation_id,
                tenant_id=tenant_id,
                recipient_hash=digest(self.ctx.settings, "invite-recipient", login),
                login_ciphertext=seal(
                    self.ctx.settings, tenant_id, "invitation", invitation_id, "login", login
                ),
                role=command.role,
                created_at=moment,
                expires_at=moment + timedelta(days=7),
            )
        )
        self.ctx.audit("invitation.requested", invitation_id, tenant_id=tenant_id)
        self.db.flush()
        self.audit(tenant_id, "tenant.user_invited", invitation_id)
        return self.ctx.save(
            "tenant.admin_invite",
            command,
            {"id": str(invitation_id), "status": "pending", "delivery": "operator"},
            tenant_id,
        )

    def users(self, limit: int, cursor: str | None, search: str) -> dict[str, Any]:
        self.operator()
        filters = {"limit": limit, "search": search}
        offset = offset_for(self.ctx, cursor, "platform-users", filters)
        statement = (
            select(User.id, User.login, User.active, UserProfile.details, PlatformOperator.active)
            .outerjoin(UserProfile, UserProfile.user_id == User.id)
            .outerjoin(PlatformOperator, PlatformOperator.user_id == User.id)
            .where(User.is_service.is_(False), User.deleted_at.is_(None))
        )
        if search:
            statement = statement.where(
                User.login.icontains(search, autoescape=True)
                | UserProfile.details["full_name"].astext.icontains(search, autoescape=True)
            )
        rows = self.db.execute(statement.order_by(User.login).offset(offset).limit(limit + 1)).all()
        return {
            "items": [
                {
                    "id": str(user_id),
                    "login": login,
                    "active": active,
                    "details": details,
                    "platform_operator": bool(operator),
                }
                for user_id, login, active, details, operator in rows[:limit]
            ],
            "next_cursor": cursor_for(
                self.ctx, offset + limit if len(rows) > limit else None, "platform-users", filters
            ),
        }

    def clinic_permissions(self, tenant_id: UUID, limit: int, cursor: str | None) -> dict[str, Any]:
        self.operator()
        filters = {"limit": limit, "clinic": str(tenant_id)}
        offset = offset_for(self.ctx, cursor, "platform-clinic-permissions", filters)
        clinic = self.permissions_context(tenant_id)
        items = clinic.memberships(limit=limit + 1, offset=offset)
        professionals = self.db.execute(
            select(Professional.id, Professional.display_name)
            .where(Professional.tenant_id == tenant_id)
            .order_by(Professional.display_name, Professional.id)
        )
        queues = self.db.execute(
            select(ServiceQueue.id, ServiceQueue.name)
            .where(ServiceQueue.tenant_id == tenant_id)
            .order_by(ServiceQueue.name, ServiceQueue.id)
        )
        return {
            "items": items[:limit],
            "professionals": [{"id": str(id_), "name": name} for id_, name in professionals],
            "queues": [{"id": str(id_), "name": name} for id_, name in queues],
            "next_cursor": cursor_for(
                self.ctx,
                offset + limit if len(items) > limit else None,
                "platform-clinic-permissions",
                filters,
            ),
        }

    def save_clinic_permissions(
        self, tenant_id: UUID, membership_id: UUID, command: MembershipDraft
    ) -> dict[str, Any]:
        self.operator(write=True)
        clinic = self.permissions_context(tenant_id)
        self.db.execute(text("SELECT public.lock_schedule(:tenant)"), {"tenant": tenant_id})
        return clinic.update_permissions(command, membership_id)

    def permissions_context(self, tenant_id: UUID) -> ClinicAdmin:
        tenant = self.db.get(Tenant, tenant_id)
        if tenant is None or tenant.deleted_at is not None or tenant.internal:
            raise PortalError()
        set_tenant(self.db, tenant_id)
        return ClinicAdmin(
            PortalContext(
                self.db,
                self.ctx.settings,
                self.ctx.identity,
                self.ctx.correlation_id,
                administrative_tenant_id=tenant_id,
            )
        )

    def set_user_status(self, command: PlatformUserStatus, user_id: UUID) -> dict[str, Any]:
        self.operator(write=True)
        replay = self.ctx.replay("platform.user_status", command, user_id)
        if replay is not None:
            return replay
        user = self.db.get(User, user_id)
        if user is None or user.deleted_at is not None:
            raise PortalError()
        changed = self.db.scalar(
            text("SELECT public.set_platform_user_active(:user_id, :active)"),
            {"user_id": user_id, "active": command.active},
        )
        if not changed:
            raise PortalError("permission_denied", 403)
        revoke_user_sessions(self.db, user_id)
        self.audit(None, "user.status_changed", user_id)
        return self.ctx.save(
            "platform.user_status", command, {"id": str(user_id), "active": command.active}, user_id
        )

    def delete_clinic(self, command: Versioned, tenant_id: UUID) -> dict[str, Any]:
        self.operator(write=True)
        replay = self.ctx.replay("tenant.delete", command, tenant_id)
        if replay is not None:
            return replay
        self.db.execute(text("SELECT public.lock_schedule(:tenant)"), {"tenant": tenant_id})
        tenant = self.db.get(Tenant, tenant_id, with_for_update=True)
        if tenant is None or tenant.deleted_at is not None or tenant.internal:
            raise PortalError()
        if tenant.version != command.version:
            raise PortalError("version_conflict", 409)
        tenant.active, tenant.deleted_at = False, now(self.db)
        tenant.version += 1
        self.db.execute(
            delete(PortalSession).where(
                PortalSession.membership_id.in_(
                    select(Membership.id).where(Membership.tenant_id == tenant_id)
                )
            )
        )
        self.audit(tenant_id, "tenant.deleted", tenant_id)
        return self.ctx.save("tenant.delete", command, {"id": str(tenant_id)}, tenant_id)

    def delete_user(self, command: Mutation, user_id: UUID) -> dict[str, Any]:
        self.operator(write=True)
        replay = self.ctx.replay("platform.user_delete", command, user_id)
        if replay is not None:
            return replay
        changed = self.db.scalar(
            text("SELECT public.archive_platform_user(:user_id)"), {"user_id": user_id}
        )
        if not changed:
            raise PortalError("permission_denied", 403)
        revoke_user_sessions(self.db, user_id)
        self.audit(None, "user.deleted", user_id)
        return self.ctx.save("platform.user_delete", command, {"id": str(user_id)}, user_id)

    def overview(self) -> dict[str, int]:
        self.operator()
        return {
            "clinics": self.db.scalar(
                select(func.count())
                .select_from(Tenant)
                .where(Tenant.deleted_at.is_(None), Tenant.internal.is_(False))
            )
            or 0,
            "active_clinics": self.db.scalar(
                select(func.count())
                .select_from(Tenant)
                .where(
                    Tenant.active.is_(True), Tenant.deleted_at.is_(None), Tenant.internal.is_(False)
                )
            )
            or 0,
            "users": self.db.scalar(
                select(func.count())
                .select_from(User)
                .where(User.deleted_at.is_(None), User.is_service.is_(False))
            )
            or 0,
            "active_users": self.db.scalar(
                select(func.count())
                .select_from(User)
                .where(User.active.is_(True), User.is_service.is_(False))
            )
            or 0,
            "operators": self.db.scalar(
                select(func.count())
                .select_from(PlatformOperator)
                .where(PlatformOperator.active.is_(True))
            )
            or 0,
        }

    def audit_events(
        self,
        limit: int,
        cursor: str | None,
        start: date | None,
        end: date | None,
        action: str,
        scope: str | None,
        clinic: UUID | None,
    ) -> dict[str, Any]:
        self.operator()
        if start and end and start > end:
            raise PortalError("validation_failed", 422)
        zone = ZoneInfo("America/Fortaleza")
        sources = []
        for label, table in (("platform", PlatformAudit), ("clinic", AuditLog)):
            if scope is not None and label != scope:
                continue
            query = select(
                literal(label).label("scope"),
                table.id,
                table.created_at,
                table.actor_id,
                table.tenant_id,
                table.action,
                table.resource_id,
                table.correlation_id,
            )
            if start:
                query = query.where(table.created_at >= datetime.combine(start, time.min, zone))
            if end:
                query = query.where(table.created_at <= datetime.combine(end, time.max, zone))
            if clinic:
                query = query.where(table.tenant_id == clinic)
            if action:
                query = query.where(table.action.icontains(action, autoescape=True))
            sources.append(query)
        events = union_all(*sources).subquery()
        actor = aliased(User)
        filters = dict(limit=limit, start=start, end=end, action=action, scope=scope, clinic=clinic)
        offset = offset_for(self.ctx, cursor, "platform-audit", filters)
        rows = (
            self.db.execute(
                select(events, actor.login.label("actor"), Tenant.name.label("clinic"))
                .outerjoin(actor, actor.id == events.c.actor_id)
                .outerjoin(Tenant, Tenant.id == events.c.tenant_id)
                .where((events.c.tenant_id.is_(None)) | Tenant.internal.is_(False))
                .order_by(events.c.created_at.desc(), events.c.id.desc(), events.c.scope)
                .offset(offset)
                .limit(limit + 1)
            )
            .mappings()
            .all()
        )
        return {
            "items": [dict(row) for row in rows[:limit]],
            "next_cursor": cursor_for(
                self.ctx, offset + limit if len(rows) > limit else None, "platform-audit", filters
            ),
        }

    def clinic_requests(self) -> dict[str, Any]:
        self.ctx.admin()
        rows = self.db.scalars(
            select(BreakGlassRequest)
            .where(BreakGlassRequest.tenant_id == self.ctx.tenant_id)
            .order_by(BreakGlassRequest.created_at.desc())
            .limit(50)
        )
        return {
            "items": [
                {
                    "id": str(row.id),
                    "appointment_id": str(row.appointment_id),
                    "status": row.status,
                    "duration_minutes": row.duration_minutes,
                    "version": row.version,
                    "reason": unseal(
                        self.ctx.settings,
                        self.ctx.tenant_id,
                        "breakglass",
                        row.id,
                        "reason",
                        row.reason_ciphertext,
                    ),
                    "expires_at": row.expires_at.isoformat() if row.expires_at else None,
                }
                for row in rows
            ]
        }

    def decide(self, command: BreakGlassDecision, request_id: UUID) -> dict[str, Any]:
        moment = self.ctx.admin(write=True)
        replay = self.ctx.replay("breakglass.decide", command, request_id)
        if replay is not None:
            return replay
        row: BreakGlassRequest = self.ctx.entity(BreakGlassRequest, request_id)
        if row.version != command.version:
            raise PortalError("version_conflict", 409)
        if row.requester_user_id == self.ctx.identity.user_id:
            raise PortalError("self_approval_denied", 403)
        if command.decision == "revoke":
            if row.status != "approved":
                raise PortalError("invalid_transition", 409)
            row.status = "revoked"
        else:
            if row.status != "pending" or moment - row.created_at > timedelta(days=1):
                raise PortalError("request_unavailable", 409)
            if command.decision == "approve":
                # Only the clinic verifies the referenced resource; pending requests prove nothing.
                self.ctx.entity(Appointment, row.appointment_id)
                row.status, row.expires_at = (
                    "approved",
                    moment + timedelta(minutes=row.duration_minutes),
                )
                row.approved_by_user_id = self.ctx.identity.user_id
            else:
                row.status = "rejected"
        row.version += 1
        self.db.add(
            AdminNotification(
                tenant_id=self.ctx.tenant_id,
                notification_type=f"breakglass.{row.status}",
                resource_id=row.id,
                created_at=moment,
            )
        )
        self.ctx.audit(f"breakglass.{row.status}", row.id)
        return self.ctx.save(
            "breakglass.decide",
            command,
            {"id": str(row.id), "status": row.status, "version": row.version},
            request_id,
        )
