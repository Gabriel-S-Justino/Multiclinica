import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.config import Settings
from backend.infrastructure.models import (
    AuditLog,
    Membership,
    Professional,
    ProfessionalAssignment,
    Tenant,
    User,
)
from backend.infrastructure.security import PASSWORDS
from backend.main import create_app


@pytest.fixture
def foundation(synthetic_password_hash):
    if not os.environ.get("TEST_ADMIN_URL"):
        if os.environ.get("CI"):
            pytest.fail("PostgreSQL real é obrigatório em CI")
        pytest.skip("Use scripts/run_integration.py ou configure TEST_ADMIN_URL")
    settings = Settings()
    admin = create_engine(os.environ["TEST_ADMIN_URL"], hide_parameters=True)
    with admin.begin() as connection:
        connection.execute(text("TRUNCATE users, tenants CASCADE"))
        connection.execute(text("TRUNCATE rate_limit_buckets"))
    ids = {
        name: uuid4()
        for name in (
            "tenant",
            "other_tenant",
            "admin",
            "collaborator",
            "reception",
            "superadmin",
            "other_user",
            "professional",
            "other_professional",
            "foreign_professional",
            "admin_member",
            "collaborator_member",
            "reception_member",
            "superadmin_member",
            "other_member",
        )
    }
    password = "test-only password 123!"  # pragma: allowlist secret (fixture sintética)
    with Session(admin) as db, db.begin():
        db.add_all(
            [
                Tenant(id=ids["tenant"], name="Clínica A"),
                Tenant(id=ids["other_tenant"], name="Clínica B"),
            ]
        )
        for name in ("admin", "collaborator", "reception", "superadmin", "other_user"):
            db.add(
                User(
                    id=ids[name],
                    login=f"{name}@test.invalid",
                    password_hash=synthetic_password_hash,
                    active=True,
                )
            )
        db.flush()
        for name, member in (
            ("admin", "admin_member"),
            ("collaborator", "collaborator_member"),
            ("reception", "reception_member"),
            ("superadmin", "superadmin_member"),
            ("other_user", "other_member"),
        ):
            db.add(
                Membership(
                    id=ids[member],
                    user_id=ids[name],
                    tenant_id=ids["other_tenant"] if name == "other_user" else ids["tenant"],
                    role="admin" if name == "other_user" else name,
                    active=True,
                )
            )
        db.add_all(
            [
                Professional(
                    id=ids["professional"],
                    tenant_id=ids["tenant"],
                    user_id=ids["collaborator"],
                    display_name="Profissional A",
                ),
                Professional(
                    id=ids["other_professional"],
                    tenant_id=ids["tenant"],
                    display_name="Profissional B",
                ),
                Professional(
                    id=ids["foreign_professional"],
                    tenant_id=ids["other_tenant"],
                    display_name="Profissional externo",
                ),
            ]
        )
        db.flush()
        db.add(
            ProfessionalAssignment(
                tenant_id=ids["tenant"],
                membership_id=ids["reception_member"],
                professional_id=ids["professional"],
            )
        )
        db.add(AuditLog(tenant_id=ids["tenant"], actor_id=ids["admin"], action="test.seed"))
    app = create_app(settings)
    with TestClient(app, base_url="https://testserver") as client:
        yield settings, admin, ids, password, client
    app.state.engine.dispose()
    admin.dispose()


@pytest.fixture(scope="session")
def synthetic_password_hash():
    return PASSWORDS.hash("test-only password 123!")  # pragma: allowlist secret (fixture sintética)


def sign_in(foundation, role="admin"):
    settings, admin, ids, password, client = foundation
    response = client.post(
        "/v1/auth/login",
        json={"login": f"{role}@test.invalid", "password": password},
        headers={"Origin": settings.public_origin},
    )
    assert response.status_code == 200, response.text
    headers = {
        "Origin": settings.public_origin,
        "X-CSRF-Token": client.cookies.get("__Host-clinic_csrf"),
    }
    response = client.post(
        "/v1/auth/active-membership",
        json={"membership_id": str(ids[f"{role}_member"])},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return {
        "Origin": settings.public_origin,
        "X-CSRF-Token": client.cookies.get("__Host-clinic_csrf"),
    }
