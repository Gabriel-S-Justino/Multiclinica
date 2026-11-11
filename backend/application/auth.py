import hmac
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pyotp
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from backend.config import Settings
from backend.domain.permissions import Principal
from backend.infrastructure.db import set_tenant
from backend.infrastructure.models import (
    AuditLog,
    Membership,
    MFAChallenge,
    PortalSession,
    RecoveryToken,
    Tenant,
    User,
)
from backend.infrastructure.security import (
    DUMMY_HASH,
    PASSWORDS,
    cipher,
    digest,
    token,
    verify_password,
)


class AuthError(Exception):
    pass


def login(
    db: Session, settings: Settings, login_name: str, password: str
) -> tuple[str, str | None]:
    user = db.scalar(select(User).where(User.login == login_name.lower()))
    valid = verify_password(user.password_hash if user else DUMMY_HASH, password)
    if not user or not valid or not user.active or user.is_service:
        raise AuthError
    if PASSWORDS.check_needs_rehash(user.password_hash):
        user.password_hash = PASSWORDS.hash(password)
    if settings.requires_mfa_for(user.id) or user.mfa_secret:
        if not user.mfa_secret:
            # Enrollment is controlled by the operator.
            raise AuthError
        challenge = token()
        db.add(
            MFAChallenge(
                token_hash=digest(settings, "challenge", challenge),
                user_id=user.id,
                expires_at=datetime.now(UTC) + timedelta(minutes=5),
            )
        )
        return challenge, None
    return create_session(db, settings, user.id, False)


def create_session(db: Session, settings: Settings, user_id: UUID, mfa: bool) -> tuple[str, str]:
    session_token, csrf_token = token(), token()
    now = datetime.now(UTC)
    db.add(
        PortalSession(
            token_hash=digest(settings, "session", session_token),
            user_id=user_id,
            csrf_hash=digest(settings, "csrf", csrf_token),
            membership_id=None,
            expires_at=now + timedelta(hours=8),
            idle_expires_at=now + timedelta(minutes=30),
            authenticated_at=now,
            mfa_verified=mfa,
        )
    )
    return session_token, csrf_token


def verify_mfa(db: Session, settings: Settings, challenge_token: str, code: str) -> tuple[str, str]:
    challenge = db.scalar(
        select(MFAChallenge)
        .where(MFAChallenge.token_hash == digest(settings, "challenge", challenge_token))
        .with_for_update()
    )
    now = datetime.now(UTC)
    if not challenge or challenge.expires_at <= now:
        raise AuthError
    user = db.scalar(select(User).where(User.id == challenge.user_id).with_for_update())
    if not user or not user.active or not user.mfa_secret:
        raise AuthError
    secret = cipher(settings).decrypt(user.mfa_secret.encode()).decode()
    step = int(now.timestamp()) // 30
    if step <= user.last_totp_step or not hmac.compare_digest(pyotp.TOTP(secret).at(now), code):
        raise AuthError
    user.last_totp_step = step
    db.delete(challenge)
    return create_session(db, settings, user.id, True)


def get_session(db: Session, settings: Settings, raw: str | None) -> PortalSession:
    if not raw or len(raw) > 128:
        raise AuthError
    session = db.scalar(
        select(PortalSession)
        .where(PortalSession.token_hash == digest(settings, "session", raw))
        .with_for_update()
    )
    now = datetime.now(UTC)
    if not session or session.expires_at <= now or session.idle_expires_at <= now:
        raise AuthError
    user = db.get(User, session.user_id)
    if not user or not user.active:
        raise AuthError
    session.idle_expires_at = min(session.expires_at, now + timedelta(minutes=30))
    db.execute(
        text("SELECT set_config('app.user_id',:actor,true)"), {"actor": str(session.user_id)}
    )
    return session


def principal(db: Session, session: PortalSession) -> Principal:
    membership = db.get(Membership, session.membership_id) if session.membership_id else None
    if not membership or not membership.active or membership.user_id != session.user_id:
        raise AuthError
    tenant = db.get(Tenant, membership.tenant_id)
    if not tenant or not tenant.active:
        raise AuthError
    set_tenant(db, membership.tenant_id)
    return Principal(
        session.user_id,
        membership.tenant_id,
        membership.id,
        membership.role,
        session.mfa_verified,
        session.authenticated_at,
        membership.can_manage_schedule,
    )


def rotate_membership(
    db: Session, settings: Settings, session: PortalSession, membership_id: UUID
) -> tuple[str, str]:
    membership = db.get(Membership, membership_id)
    if not membership or membership.user_id != session.user_id or not membership.active:
        raise AuthError
    new_token, csrf = create_session(db, settings, session.user_id, session.mfa_verified)
    db.flush()
    replacement = db.get(PortalSession, digest(settings, "session", new_token))
    if replacement is None:
        raise AuthError
    replacement.membership_id = membership.id
    replacement.expires_at = session.expires_at
    replacement.authenticated_at = session.authenticated_at
    set_tenant(db, membership.tenant_id)
    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            actor_id=session.user_id,
            action="session.membership_selected",
            resource_id=membership.id,
        )
    )
    db.delete(session)
    return new_token, csrf


def revoke_user_sessions(db: Session, user_id: UUID) -> None:
    db.execute(delete(PortalSession).where(PortalSession.user_id == user_id))
    db.execute(delete(MFAChallenge).where(MFAChallenge.user_id == user_id))


def complete_recovery(db: Session, settings: Settings, raw: str, password: str) -> None:
    recovery = db.scalar(
        select(RecoveryToken)
        .where(RecoveryToken.token_hash == digest(settings, "recovery", raw))
        .with_for_update()
    )
    if not recovery or recovery.expires_at <= datetime.now(UTC):
        raise AuthError
    user = db.scalar(select(User).where(User.id == recovery.user_id).with_for_update())
    if not user or not user.active:
        raise AuthError
    user.password_hash = PASSWORDS.hash(password)
    revoke_user_sessions(db, user.id)
    db.execute(delete(RecoveryToken).where(RecoveryToken.user_id == user.id))
