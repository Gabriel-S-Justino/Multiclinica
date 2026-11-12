"""Tests for authenticated, MFA-protected self-service password changes."""

import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.application import auth
from backend.config import Settings
from backend.infrastructure.models import (
    AuditLog,
    Membership,
    MFAChallenge,
    PortalSession,
    RecoveryToken,
    Tenant,
    User,
)
from backend.infrastructure.security import PASSWORDS, verify_password


@pytest.fixture
def account(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for model in (User, Tenant, Membership, PortalSession, MFAChallenge, RecoveryToken, AuditLog):
        model.__table__.create(engine)
    monkeypatch.setattr(auth, "set_tenant", lambda *_: None)
    initial = secrets.token_urlsafe(24)
    replacement = secrets.token_urlsafe(24)
    settings = Settings(
        app_env="test",
        database_url=SecretStr("postgresql+psycopg://user:placeholder@localhost/neondb"),
        public_origin="https://example.invalid",
        token_key=SecretStr(secrets.token_hex(32)),
        field_key=SecretStr(Fernet.generate_key().decode()),
    )
    uid, tid = uuid4(), uuid4()
    with Session(engine) as db, db.begin():
        db.add(
            User(
                id=uid,
                login="test@example.invalid",
                password_hash=PASSWORDS.hash(initial),
                active=True,
                is_service=False,
                last_totp_step=-1,
                mfa_secret="configured-in-test",
            )
        )
        db.add(Tenant(id=tid, name="Test", active=True, timezone="America/Sao_Paulo"))
        db.flush()
        membership = Membership(id=uuid4(), tenant_id=tid, user_id=uid, role="admin", active=True)
        db.add(membership)
        session = PortalSession(
            token_hash="0" * 64,
            user_id=uid,
            membership_id=membership.id,
            csrf_hash="1" * 64,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            idle_expires_at=datetime.now(UTC) + timedelta(minutes=30),
            authenticated_at=datetime.now(UTC),
            mfa_verified=True,
        )
        db.add(session)
    yield engine, settings, uid, initial, replacement
    engine.dispose()


def test_changes_hash_and_revokes_active_sessions(account):
    engine, settings, uid, initial, replacement = account
    with Session(engine) as db, db.begin():
        session = db.get(PortalSession, "0" * 64)
        auth.change_authenticated_password(db, settings, session, initial, replacement)
    with Session(engine) as db:
        user = db.get(User, uid)
        assert user is not None
        assert verify_password(user.password_hash, replacement)
        assert not verify_password(user.password_hash, initial)
        assert db.get(PortalSession, "0" * 64) is None
        assert list(db.scalars(select(AuditLog.action))) == ["auth.password_changed"]


@pytest.mark.parametrize("failure", ["bad_current", "same", "without_mfa", "stale_mfa"])
def test_rejects_invalid_changes_without_mutation(account, failure):
    engine, settings, uid, initial, replacement = account
    with pytest.raises(auth.AuthError), Session(engine) as db, db.begin():
        session = db.get(PortalSession, "0" * 64)
        assert session is not None
        if failure == "without_mfa":
            session.mfa_verified = False
        if failure == "stale_mfa":
            session.authenticated_at = datetime.now(UTC) - timedelta(minutes=16)
        provided = secrets.token_urlsafe(20) if failure == "bad_current" else initial
        new_value = initial if failure == "same" else replacement
        auth.change_authenticated_password(db, settings, session, provided, new_value)
    with Session(engine) as db:
        user = db.get(User, uid)
        assert user is not None and verify_password(user.password_hash, initial)
        assert db.get(PortalSession, "0" * 64) is not None
        assert not list(db.scalars(select(AuditLog)))


def test_authenticated_endpoint_requires_csrf_and_changes_password(account, monkeypatch):
    from fastapi.testclient import TestClient

    from backend.infrastructure.security import digest
    from backend.main import create_app

    engine, settings, uid, initial, replacement = account
    csrf_value = secrets.token_urlsafe(18)
    with Session(engine) as db, db.begin():
        session = db.get(PortalSession, "0" * 64)
        assert session is not None
        session.csrf_hash = digest(settings, "csrf", csrf_value)

    def get_test_session(db, *_):
        return db.get(PortalSession, "0" * 64)

    monkeypatch.setattr(auth, "get_session", get_test_session)
    monkeypatch.setattr("backend.main.consume", lambda *_: True)
    app = create_app(settings, engine)
    client = TestClient(app)
    payload = {"current_password": initial, "new_password": replacement}
    invalid = client.post(
        "/v1/auth/password/change-authenticated",
        json=payload,
        headers={"Origin": "https://other.invalid", "X-CSRF-Token": csrf_value},
    )
    assert invalid.status_code == 403
    response = client.post(
        "/v1/auth/password/change-authenticated",
        json=payload,
        headers={"Origin": settings.public_origin, "X-CSRF-Token": csrf_value},
    )
    assert response.status_code == 204
    with Session(engine) as db:
        user = db.get(User, uid)
        assert user is not None and verify_password(user.password_hash, replacement)
        assert db.get(PortalSession, "0" * 64) is None
