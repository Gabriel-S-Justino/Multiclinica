from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pyotp
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from backend.infrastructure.db import set_tenant
from backend.infrastructure.models import (
    Membership,
    PortalSession,
    ProfessionalAssignment,
    RecoveryToken,
    User,
)
from backend.infrastructure.rate_limit import consume
from backend.infrastructure.security import cipher, digest, token
from tests.integration.conftest import sign_in


@pytest.mark.parametrize(
    "role,visible",
    [
        ("admin", {"professional", "other_professional"}),
        ("collaborator", {"professional"}),
        ("reception", {"professional"}),
        ("superadmin", set()),
    ],
)
def test_endpoint_rbac_and_tenant_isolation(foundation, role, visible):
    _, _, ids, _, client = foundation
    sign_in(foundation, role)
    result = client.get("/v1/professionals")
    assert result.status_code == 200
    assert {item["id"] for item in result.json()["items"]} == {str(ids[key]) for key in visible}
    for name in ("professional", "other_professional", "foreign_professional"):
        assert client.get(f"/v1/professionals/{ids[name]}").status_code == (
            200 if name in visible else 404
        )
    assert client.get("/v1/audit").status_code == 403  # no verified MFA in test-only password flow


def test_csrf_rotation_revocation_and_tenant_input(foundation):
    settings, _, ids, _, client = foundation
    headers = sign_in(foundation)
    old_cookie = client.cookies.get("__Host-clinic_session")
    assert client.post("/v1/auth/logout", json={}).status_code == 403
    assert (
        client.post(
            "/v1/auth/logout", json={}, headers={**headers, "Origin": "https://attacker.invalid"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/v1/auth/active-membership",
            json={"membership_id": str(ids["other_member"])},
            headers=headers,
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/v1/auth/active-membership",
            json={"membership_id": str(ids["admin_member"]), "tenant_id": str(ids["other_tenant"])},
            headers=headers,
        ).status_code
        == 422
    )
    response = client.post(
        "/v1/auth/active-membership",
        json={"membership_id": str(ids["admin_member"])},
        headers=headers,
    )
    assert response.status_code == 200
    new_cookie = client.cookies.get("__Host-clinic_session")
    assert old_cookie != new_cookie
    client.cookies.set("__Host-clinic_session", old_cookie, domain="testserver.local", path="/")
    assert client.get("/v1/auth/session").status_code == 401
    client.cookies.set("__Host-clinic_session", new_cookie, domain="testserver.local", path="/")
    headers = {
        "Origin": settings.public_origin,
        "X-CSRF-Token": client.cookies.get("__Host-clinic_csrf"),
    }
    assert client.post("/v1/auth/logout", json={}, headers=headers).status_code == 204
    assert client.get("/v1/auth/session").status_code == 401


def test_revoked_membership_and_expiration(foundation):
    _, admin, ids, _, client = foundation
    sign_in(foundation, "collaborator")
    with Session(admin) as db, db.begin():
        db.get(Membership, ids["collaborator_member"]).active = False
    assert client.get("/v1/professionals").status_code == 401
    with Session(admin) as db, db.begin():
        session = db.scalar(select(PortalSession))
        session.idle_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert client.get("/v1/auth/session").status_code == 401


def test_rls_absent_context_connection_reuse_and_audit_immutable(foundation):
    _, _, ids, _, client = foundation
    engine = client.app.state.engine
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM professionals")) == 0
        connection.commit()
        with connection.begin():
            connection.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(ids["tenant"])}
            )
            assert connection.scalar(text("SELECT count(*) FROM professionals")) == 2
        with connection.begin():
            assert connection.scalar(text("SELECT count(*) FROM professionals")) == 0
    with Session(engine) as db, db.begin():
        set_tenant(db, ids["tenant"])
        assert db.scalar(text("SELECT count(*) FROM audit_logs")) == 1
    for statement in (
        "UPDATE audit_logs SET action='changed'",
        "DELETE FROM audit_logs",
        "TRUNCATE audit_logs",
        "UPDATE users SET active=false",
        "DELETE FROM professionals",
    ):
        with pytest.raises(DBAPIError), engine.begin() as connection:
            connection.execute(text(statement))


def test_cross_tenant_fk_rejected(foundation):
    _, admin, ids, _, _ = foundation
    with pytest.raises(IntegrityError), Session(admin) as db, db.begin():
        db.add(
            ProfessionalAssignment(
                tenant_id=ids["tenant"],
                membership_id=ids["reception_member"],
                professional_id=ids["foreign_professional"],
            )
        )


def test_rls_rejects_foreign_audit_insert(foundation):
    _, _, ids, _, client = foundation
    with pytest.raises(DBAPIError), Session(client.app.state.engine) as db, db.begin():
        set_tenant(db, ids["tenant"])
        db.execute(
            text(
                "INSERT INTO audit_logs(id,tenant_id,actor_id,action) VALUES (gen_random_uuid(),:tenant,:actor,'forbidden')"
            ),
            {"tenant": ids["other_tenant"], "actor": ids["admin"]},
        )


def test_startup_rejects_privileged_database_role(foundation):
    from fastapi.testclient import TestClient

    from backend.main import create_app

    settings, admin, _, _, _ = foundation
    with pytest.raises(RuntimeError, match="runtime"), TestClient(create_app(settings, admin)):
        pass


def test_login_errors_uniform_rate_limit_persisted_and_safe_logs(foundation, caplog):
    settings, _, _, _, client = foundation
    caplog.set_level("INFO", logger="clinic.requests")
    body = {
        "login": "missing@test.invalid",
        "password": "SECRET-CANARY-DO-NOT-LOG",  # pragma: allowlist secret (canário sintético)
    }  # pragma: allowlist secret (canário sintético)
    first = client.post("/v1/auth/login", json=body, headers={"Origin": settings.public_origin})
    second = client.post(
        "/v1/auth/login",
        json={**body, "login": "admin@test.invalid"},
        headers={"Origin": settings.public_origin},
    )
    assert first.status_code == second.status_code == 401
    assert first.json()["error"]["code"] == second.json()["error"]["code"]
    assert "SECRET-CANARY" not in caplog.text
    # A fixed five-minute bucket may turn while real password verification runs.
    # Seventeen attempts guarantee exceeding eight in one of two adjacent buckets.
    for _ in range(17):
        response = client.post(
            "/v1/auth/login", json=body, headers={"Origin": settings.public_origin}
        )
        if response.status_code == 429:
            break
    assert response.status_code == 429
    assert "Secure" in first.headers.get("set-cookie", "Secure")


def test_rate_limit_is_atomic(foundation):
    settings, _, _, _, client = foundation
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(
                lambda _: consume(client.app.state.engine, settings, "concurrency", "test", 5),
                range(20),
            )
        )
    assert sum(results) == 5


def test_mfa_cookie_flags_replay_and_audit_permission(foundation):
    settings, admin, ids, password, client = foundation
    secret = pyotp.random_base32()
    with Session(admin) as db, db.begin():
        db.get(User, ids["admin"]).mfa_secret = cipher(settings).encrypt(secret.encode()).decode()
    origin = {"Origin": settings.public_origin}
    challenge = client.post(
        "/v1/auth/login", json={"login": "admin@test.invalid", "password": password}, headers=origin
    ).json()["challenge"]
    assert client.get("/v1/auth/session").status_code == 401
    result = client.post(
        "/v1/auth/mfa/verify",
        json={"challenge": challenge, "code": pyotp.TOTP(secret).now()},
        headers=origin,
    )
    assert result.status_code == 200, result.text
    cookie_headers = result.headers.get_list("set-cookie")
    assert any(
        "HttpOnly" in value and "Secure" in value and "SameSite=lax" in value
        for value in cookie_headers
    )
    assert (
        client.post(
            "/v1/auth/mfa/verify",
            json={"challenge": challenge, "code": pyotp.TOTP(secret).now()},
            headers=origin,
        ).status_code
        == 401
    )
    headers = {**origin, "X-CSRF-Token": client.cookies.get("__Host-clinic_csrf")}
    assert (
        client.post(
            "/v1/auth/active-membership",
            json={"membership_id": str(ids["admin_member"])},
            headers=headers,
        ).status_code
        == 200
    )
    assert client.get("/v1/audit").status_code == 200
    # A second challenge cannot replay the same TOTP step.
    challenge2 = client.post(
        "/v1/auth/login", json={"login": "admin@test.invalid", "password": password}, headers=origin
    ).json()["challenge"]
    assert (
        client.post(
            "/v1/auth/mfa/verify",
            json={"challenge": challenge2, "code": pyotp.TOTP(secret).now()},
            headers=origin,
        ).status_code
        == 401
    )


def test_recovery_single_use_revokes_sessions(foundation):
    settings, admin, ids, _, client = foundation
    sign_in(foundation)
    raw = token()
    with Session(admin) as db, db.begin():
        db.add(
            RecoveryToken(
                token_hash=digest(settings, "recovery", raw),
                user_id=ids["admin"],
                expires_at=datetime.now(UTC) + timedelta(minutes=5),
            )
        )
    body = {
        "token": raw,
        "password": "replacement password 123!",  # pragma: allowlist secret (fixture sintética)
    }  # pragma: allowlist secret (fixture sintética)
    headers = {"Origin": settings.public_origin}
    assert client.post("/v1/auth/recovery/confirm", json=body, headers=headers).status_code == 204
    assert client.get("/v1/auth/session").status_code == 401
    assert client.post("/v1/auth/recovery/confirm", json=body, headers=headers).status_code == 401
    assert (
        client.post(
            "/v1/auth/login",
            json={"login": "admin@test.invalid", "password": body["password"]},
            headers=headers,
        ).status_code
        == 200
    )


def test_payload_cors_security_headers_and_readiness(foundation):
    _, _, _, _, client = foundation
    response = client.get("/v1/health")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"
    assert client.get("/v1/ready").status_code == 200
    response = client.post("/v1/auth/login", content=b"x" * 65537)
    assert response.status_code == 413
    response = client.options(
        "/v1/auth/login",
        headers={"Origin": "https://attacker.invalid", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in response.headers
