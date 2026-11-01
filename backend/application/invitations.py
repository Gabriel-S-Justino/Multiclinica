from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.application.portal_access import PortalError, now
from backend.config import Settings
from backend.infrastructure.db import set_tenant
from backend.infrastructure.models import AuditLog, Membership, PortalSession, Tenant, User
from backend.infrastructure.portal_models import Invitation
from backend.infrastructure.security import digest


def recipient_context(db: Session, settings: Settings, session: PortalSession) -> str:
    user = db.get(User, session.user_id)
    if not user or not user.active:
        raise PortalError("permission_denied", 403)
    value = digest(settings, "invite-recipient", user.login.lower())
    db.execute(text("SELECT set_config('app.invite_recipient',:value,true)"), {"value": value})
    return value


def list_invitations(db: Session, settings: Settings, session: PortalSession) -> dict[str, Any]:
    recipient = recipient_context(db, settings, session)
    rows = db.execute(
        select(Invitation, Tenant)
        .join(Tenant, Tenant.id == Invitation.tenant_id)
        .where(
            Invitation.recipient_hash == recipient,
            Invitation.status == "pending",
            Invitation.expires_at > now(db),
            Tenant.active.is_(True),
        )
        .limit(50)
    )
    return {
        "items": [
            {
                "id": str(row.id),
                "clinic_name": tenant.name,
                "role": row.role,
                "expires_at": row.expires_at.isoformat(),
            }
            for row, tenant in rows
        ]
    }


def accept_invitation(
    db: Session,
    settings: Settings,
    session: PortalSession,
    invitation_id: UUID,
    correlation_id: UUID,
) -> dict[str, Any]:
    recipient = recipient_context(db, settings, session)
    row = db.scalar(
        select(Invitation).where(
            Invitation.id == invitation_id, Invitation.recipient_hash == recipient
        )
    )
    if row is None:
        raise PortalError()
    set_tenant(db, row.tenant_id)
    db.execute(text("SELECT public.lock_schedule(:tenant)"), {"tenant": row.tenant_id})
    db.refresh(row, with_for_update=True)
    tenant = db.get(Tenant, row.tenant_id)
    if (
        not tenant
        or not tenant.active
        or row.expires_at <= now(db)
        or row.status not in {"pending", "accepted"}
    ):
        raise PortalError("invitation_unavailable", 409)
    if (settings.mfa_required or row.role == "admin") and not session.mfa_verified:
        raise PortalError("reauthentication_required", 403)
    member = db.scalar(
        select(Membership).where(
            Membership.tenant_id == row.tenant_id, Membership.user_id == session.user_id
        )
    )
    if row.status == "accepted":
        if not member or not member.active:
            raise PortalError("invitation_unavailable", 409)
        return {"membership_id": str(member.id), "status": "accepted"}
    if member and member.active:
        raise PortalError("membership_already_active", 409)
    if member is None:
        member = Membership(
            tenant_id=row.tenant_id, user_id=session.user_id, role=row.role, active=True
        )
        db.add(member)
    else:
        if member.role == "superadmin":
            raise PortalError("permission_denied", 403)
        member.role, member.active, member.can_manage_schedule = row.role, True, False
    row.status = "accepted"
    db.flush()
    db.add(
        AuditLog(
            tenant_id=row.tenant_id,
            actor_id=session.user_id,
            action="invitation.accepted",
            resource_id=row.id,
            correlation_id=correlation_id,
        )
    )
    return {"membership_id": str(member.id), "status": "accepted"}
