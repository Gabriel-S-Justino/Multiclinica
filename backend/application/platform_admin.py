from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, text

from backend.application.auth import revoke_user_sessions
from backend.application.pagination import cursor_for, offset_for
from backend.application.portal_access import PortalContext, PortalError, now
from backend.application.portal_commands import (
    BreakGlassDecision,
    InvitationDraft,
    PlatformUserStatus,
    TenantDraft,
)
from backend.infrastructure.db import set_tenant
from backend.infrastructure.fields import seal, unseal
from backend.infrastructure.models import Tenant, User, UserProfile
from backend.infrastructure.portal_models import (
    AdminNotification,
    BreakGlassRequest,
    Invitation,
    PlatformAudit,
    PlatformOperator,
)
from backend.infrastructure.scheduling_models import Appointment
from backend.infrastructure.security import digest


class PlatformAdmin:
    def __init__(self, ctx: PortalContext) -> None:
        self.ctx, self.db = ctx, ctx.db

    def operator(self, *, write: bool = False) -> None:
        self.ctx.validate(lock=write, roles={"superadmin"}, recent=write)
        operator = self.db.get(PlatformOperator, self.ctx.identity.user_id)
        if not operator or not operator.active or not self.ctx.identity.mfa_verified:
            raise PortalError("permission_denied", 403)

    def audit(self, tenant_id: UUID, action: str, resource_id: UUID | None) -> None:
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
                select(Tenant).order_by(Tenant.name, Tenant.id).offset(offset).limit(limit + 1)
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
        if row is None:
            raise PortalError()
        if command.version != (row.version if tenant_id else 0):
            raise PortalError("version_conflict", 409)
        if row.id == self.ctx.tenant_id and not command.active:
            raise PortalError("platform_tenant_required", 409)
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

    def invite_user(self, command: InvitationDraft, tenant_id: UUID) -> dict[str, Any]:
        self.operator(write=True)
        replay = self.ctx.replay("tenant.admin_invite", command, tenant_id)
        if replay is not None:
            return replay
        tenant = self.db.get(Tenant, tenant_id)
        if not tenant or not tenant.active or tenant_id == self.ctx.tenant_id:
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
        set_tenant(self.db, self.ctx.tenant_id)
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
            .where(User.is_service.is_(False))
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

    def set_user_status(self, command: PlatformUserStatus, user_id: UUID) -> dict[str, Any]:
        self.operator(write=True)
        replay = self.ctx.replay("platform.user_status", command, user_id)
        if replay is not None:
            return replay
        changed = self.db.scalar(
            text("SELECT public.set_platform_user_active(:user_id, :active)"),
            {"user_id": user_id, "active": command.active},
        )
        if not changed:
            raise PortalError("permission_denied", 403)
        revoke_user_sessions(self.db, user_id)
        self.audit(self.ctx.tenant_id, "user.status_changed", user_id)
        return self.ctx.save(
            "platform.user_status", command, {"id": str(user_id), "active": command.active}, user_id
        )

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
