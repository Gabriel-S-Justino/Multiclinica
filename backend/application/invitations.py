import hmac
import re
from typing import Any
from uuid import UUID

import pyotp
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.application import auth
from backend.application.portal_access import PortalError, now
from backend.config import Settings
from backend.infrastructure.db import set_tenant
from backend.infrastructure.models import AuditLog, Membership, PortalSession, Tenant, User
from backend.infrastructure.portal_models import Invitation
from backend.infrastructure.security import PASSWORDS, cipher, digest


def activation_receipt(settings: Settings, receipt: dict[str, Any]) -> dict[str, Any]:
    invitation_id = receipt["id"]
    signature = digest(settings, "invitation-activation", invitation_id)
    return {**receipt, "activation_code": f"{invitation_id}.{signature}"}


def activation_invitation(db: Session, settings: Settings, login: str, code: str) -> Invitation:
    raw_id, _, signature = code.partition(".")
    if not hmac.compare_digest(digest(settings, "invitation-activation", raw_id), signature):
        raise PortalError("activation_unavailable", 409)

    recipient = digest(settings, "invite-recipient", login)
    db.execute(text("SELECT set_config('app.invite_recipient',:value,true)"), {"value": recipient})
    invitation = db.scalar(
        select(Invitation)
        .join(Tenant, Tenant.id == Invitation.tenant_id)
        .where(
            Invitation.id == UUID(raw_id),
            Invitation.recipient_hash == recipient,
            Invitation.status == "pending",
            Invitation.expires_at > now(db),
            Tenant.active.is_(True),
        )
    )
    if invitation is None or db.scalar(select(User.id).where(User.login == login)) is not None:
        raise PortalError("activation_unavailable", 409)
    return invitation


def activate_account(
    db: Session,
    settings: Settings,
    login: str,
    code: str,
    password: str,
    secret: str,
    totp_code: str,
    correlation_id: UUID,
) -> tuple[str, str]:
    invitation = activation_invitation(db, settings, login, code)
    moment = now(db)
    if not re.fullmatch(r"[A-Z2-7]{32}", secret) or not hmac.compare_digest(
        pyotp.TOTP(secret).at(moment), totp_code
    ):
        raise PortalError("activation_mfa_invalid", 422)

    set_tenant(db, invitation.tenant_id)
    db.execute(text("SELECT public.lock_schedule(:tenant)"), {"tenant": invitation.tenant_id})
    user_id = db.scalar(
        text(
            "SELECT public.activate_invited_user(:invite, :login, :recipient, :password, :mfa, :step)"
        ),
        {
            "invite": invitation.id,
            "login": login,
            "recipient": invitation.recipient_hash,
            "password": PASSWORDS.hash(password),
            "mfa": cipher(settings).encrypt(secret.encode()).decode(),
            "step": int(moment.timestamp()) // 30,
        },
    )
    if user_id is None:
        raise PortalError("activation_unavailable", 409)

    session_token, csrf = auth.create_session(db, settings, user_id, True)
    db.flush()
    session = auth.get_session(db, settings, session_token)
    accept_invitation(db, settings, session, invitation.id, correlation_id)
    return session_token, csrf


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
