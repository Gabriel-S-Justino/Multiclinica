from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import UUID, uuid4

import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from backend.infrastructure.fields import unseal
from backend.infrastructure.models import Membership, PortalSession, User
from backend.infrastructure.portal_models import (
    ClinicPolicy,
    IntegrationConfig,
    Message,
    PlatformOperator,
    QueueMembership,
    ServiceQueue,
)
from backend.infrastructure.scheduling_models import (
    ConversationState,
    OutboxEvent,
    Service,
)
from backend.infrastructure.security import cipher
from tests.integration.test_scheduling import scheduling  # noqa: F401


@dataclass
class PortalHarness:
    h: object
    client: object
    password: str
    secrets: dict
    cookies: dict = field(default_factory=dict)

    def login(self, role="admin"):
        self.client.cookies.clear()
        if role in self.cookies:
            self.client.cookies.update(self.cookies[role])
            return
        origin = {"Origin": self.h.settings.public_origin}
        response = self.client.post(
            "/v1/auth/login",
            json={"login": f"{role}@test.invalid", "password": self.password},
            headers=origin,
        )
        assert response.status_code == 200, response.text
        if "challenge" in response.json():
            result = self.client.post(
                "/v1/auth/mfa/verify",
                json={
                    "challenge": response.json()["challenge"],
                    "code": pyotp.TOTP(self.secrets[role]).now(),
                },
                headers=origin,
            )
            assert result.status_code == 200, result.text
        member = "other_member" if role == "other_user" else f"{role}_member"
        if role == "superadmin":
            current = self.client.get("/v1/auth/session")
            assert current.json()["platform_access"]
            assert current.json()["active_membership_id"] is None
            assert not current.json()["memberships"]
            self.cookies[role] = dict(self.client.cookies)
            return
        response = self.client.post(
            "/v1/auth/active-membership",
            json={"membership_id": str(self.h.ids[member])},
            headers=self.headers(),
        )
        assert response.status_code == 200, response.text
        self.cookies[role] = dict(self.client.cookies)

    def headers(self):
        return {
            "Origin": self.h.settings.public_origin,
            "X-CSRF-Token": self.client.cookies.get("__Host-clinic_csrf", ""),
        }

    def call(self, method, path, body=None, *, expected=None):
        headers = self.headers()
        if body and "idempotency_key" in body:
            headers["Idempotency-Key"] = body["idempotency_key"]
        response = self.client.request(method, path, json=body, headers=headers)
        if expected is not None:
            assert response.status_code == expected, (path, response.status_code, response.text)
        return response

    def command(self, **values):
        return {"idempotency_key": uuid4().hex, **values}

    def hold(self, **values):
        body = dict(
            service_id=str(self.h.ids["service"]),
            unit_id=str(self.h.ids["unit"]),
            professional_id=str(self.h.ids["professional"]),
            contact_id=str(self.h.ids["contact"]),
            starts_at=self.h.start.isoformat(),
        )
        return self.call("POST", "/v1/holds", self.command(**(body | values)), expected=200).json()

    def period(self):
        day = self.h.start.date().isoformat()
        return f"first_date={day}&last_date={day}"


@pytest.fixture
def portal(foundation, request):
    settings, admin, _, password, client = foundation
    h = request.getfixturevalue("scheduling")
    h.ids |= {name: uuid4() for name in ("queue", "foreign_queue")}
    secrets = {
        role: pyotp.random_base32()
        for role in ("admin", "reception", "collaborator", "superadmin", "other_user")
    }
    with Session(admin) as db, db.begin():
        for role, secret in secrets.items():
            db.get(User, h.ids[role]).mfa_secret = (
                cipher(settings).encrypt(secret.encode()).decode()
            )
        db.add(PlatformOperator(user_id=h.ids["superadmin"], active=True))
        db.add(
            ClinicPolicy(
                tenant_id=h.ids["tenant"],
                identity_policy_approved=True,
                identity_policy_reference="SYNTHETIC-POLICY",
                verification_ttl_minutes=60,
                version=0,
            )
        )
        hours = [{"weekday": day, "start_minute": 0, "end_minute": 1440} for day in range(7)]
        db.add(
            ServiceQueue(
                id=h.ids["queue"],
                tenant_id=h.ids["tenant"],
                name="Fila sintética",
                kind="general",
                active=True,
                hours=hours,
                outside_hours_notice="Solicitação registrada para o próximo expediente.",
                version=0,
            )
        )
        db.add(
            ServiceQueue(
                id=h.ids["foreign_queue"],
                tenant_id=h.ids["other_tenant"],
                name="Fila externa",
                kind="financial",
                active=True,
                hours=hours,
                outside_hours_notice="Solicitação registrada.",
                version=0,
            )
        )
        db.flush()
        db.add_all(
            QueueMembership(
                tenant_id=h.ids["tenant"],
                queue_id=h.ids["queue"],
                membership_id=h.ids[f"{role}_member"],
            )
            for role in ("admin", "reception")
        )
    return PortalHarness(h, client, password, secrets)


@pytest.mark.parametrize("role", ["admin", "reception", "collaborator", "superadmin"])
def test_read_endpoint_role_matrix(portal, role):
    p = portal
    p.login(role)
    clinic = role != "superadmin"
    expectations = {
        "/portal/catalog": 200 if clinic else 403,
        "/services": 200 if role == "admin" else 403,
        "/team/professionals": 200 if role == "admin" else 403,
        "/team/memberships": 200 if role == "admin" else 403,
        "/units": 200 if role == "admin" else 403,
        "/clinic-policy": 200 if role == "admin" else 403,
        "/admin/queues": 200 if role == "admin" else 403,
        "/integrations": 200 if role == "admin" else 403,
        "/audit": 200 if role == "admin" else 403,
        "/notifications": 200 if role == "admin" else 403,
        "/support-requests": 200 if role == "admin" else 403,
        "/queues": 200 if role in {"admin", "reception"} else 403,
        "/inbox": 200 if role in {"admin", "reception"} else 403,
        f"/appointments?{p.period()}": 200 if clinic else 403,
        f"/schedules?professional_id={p.h.ids['professional']}": 200 if clinic else 403,
        "/platform/tenants": 200 if role == "superadmin" else 403,
    }
    for path, status in expectations.items():
        p.call("GET", "/v1" + path, expected=status)


def test_http_booking_review_verification_reschedule_and_cancel(portal):
    p = portal
    p.login()
    hold = p.hold()
    summary = p.call("GET", f"/v1/holds/{hold['hold_id']}/summary", expected=200).json()
    assert summary["service_name"] == "Serviço sintético" and summary["duration_minutes"] == 30
    result = p.call(
        "POST",
        "/v1/appointments",
        p.command(
            hold_id=hold["hold_id"],
            contact_id=str(p.h.ids["contact"]),
            new_patient={"display_name": "Paciente sintético HTTP", "purpose_acknowledged": True},
        ),
        expected=200,
    ).json()
    appointment_id = result["appointment_id"]
    view = p.call("GET", f"/v1/appointments/{appointment_id}", expected=200).json()
    assert view["patient_name"] == "Paciente sintético HTTP" and view["actions"] == [
        "verify_identity"
    ]
    p.call(
        "POST",
        "/v1/patient-verifications",
        p.command(
            patient_id=result["patient_id"],
            contact_id=str(p.h.ids["contact"]),
            relationship="dependent",
            identity_checked=True,
            authority_checked=True,
            evidence_reference="SYNTHETIC-CHECK",
        ),
        expected=200,
    )
    view = p.call("GET", f"/v1/appointments/{appointment_id}", expected=200).json()
    assert "reschedule" in view["actions"] and view["identity_verified"]
    replacement_hold = p.hold(
        starts_at=(p.h.start + timedelta(minutes=15)).isoformat(),
        reschedule_appointment_id=appointment_id,
        appointment_version=0,
    )
    replacement = p.call(
        "POST",
        f"/v1/appointments/{appointment_id}/reschedule",
        p.command(
            appointment_id=appointment_id,
            contact_id=str(p.h.ids["contact"]),
            version=0,
            hold_id=replacement_hold["hold_id"],
        ),
        expected=200,
    ).json()
    new_id = replacement["appointment_id"]
    assert (
        p.call("GET", f"/v1/appointments/{appointment_id}", expected=200).json()["status"]
        == "rescheduled"
    )
    body = p.command(appointment_id=new_id, contact_id=str(p.h.ids["contact"]), version=0)
    assert (
        p.call("POST", f"/v1/appointments/{new_id}/cancel", body, expected=200).json()["status"]
        == "canceled"
    )
    assert (
        p.call("POST", f"/v1/appointments/{new_id}/cancel", body, expected=200).json()["version"]
        == 1
    )


def service_body(p, **changes):
    base = dict(
        version=0,
        name="Serviço HTTP",
        display_order=1,
        active=True,
        requires_professional=True,
        policy_validated=False,
        requires_birth_date=False,
        duration_minutes=30,
        step_minutes=15,
        buffer_before=0,
        buffer_after=0,
        min_notice_minutes=0,
        cancellation_notice_minutes=0,
        reschedule_notice_minutes=0,
        horizon_days=7,
        max_reschedules=2,
        hold_ttl_minutes=10,
        required_resource_ids=[],
    )
    return p.command(**(base | changes))


def test_service_crud_versions_and_request_idempotency(portal):
    p = portal
    p.login()
    body = service_body(p)
    result = p.call("POST", "/v1/services", body, expected=200).json()
    assert p.call("POST", "/v1/services", body, expected=200).json() == result
    assert result["version"] == 1
    updated = p.call(
        "PATCH",
        f"/v1/services/{result['id']}",
        service_body(p, version=1, name="Serviço alterado", display_order=2),
        expected=200,
    ).json()
    p.call("PATCH", f"/v1/services/{result['id']}", service_body(p, version=1), expected=409)
    p.call(
        "DELETE",
        f"/v1/services/{result['id']}",
        p.command(version=updated["version"]),
        expected=200,
    )
    with Session(p.h.admin) as db:
        assert db.get(Service, UUID(result["id"])).active is False


def test_financial_service_routes_to_queue_without_clinical_defaults(portal):
    p = portal
    p.login()
    result = p.call(
        "POST",
        "/v1/services",
        p.command(
            version=0,
            name="Financeiro",
            display_order=1,
            active=True,
            requires_professional=False,
            policy_validated=False,
            requires_birth_date=False,
            service_queue_id=str(p.h.ids["queue"]),
        ),
        expected=200,
    ).json()
    assert result["id"]
    p.call(
        "POST",
        "/v1/services",
        p.command(
            version=0,
            name="Sem fila",
            display_order=0,
            active=True,
            requires_professional=False,
            policy_validated=False,
            requires_birth_date=False,
        ),
        expected=422,
    )


def test_http_tenant_professional_idor_and_cursor_scope(portal):
    p = portal
    original = p.h.confirm(p.h.hold())
    p.login("other_user")
    p.call("GET", f"/v1/appointments/{original['appointment_id']}", expected=404)
    p.call("GET", f"/v1/contacts/{p.h.ids['contact']}/patients", expected=404)
    p.call(
        "POST",
        f"/v1/appointments/{original['appointment_id']}/cancel",
        p.command(
            appointment_id=original["appointment_id"], contact_id=str(p.h.ids["contact"]), version=0
        ),
        expected=404,
    )
    p.login()
    availability = f"/v1/availability?service_id={p.h.ids['service']}&unit_id={p.h.ids['unit']}&professional_id={p.h.ids['professional']}&{p.period()}&limit=1"
    cursor = p.call("GET", availability, expected=200).json()["next_cursor"]
    assert cursor
    p.call("GET", availability + "&cursor=" + cursor, expected=200)
    p.login("reception")
    p.call("GET", availability + "&cursor=" + cursor, expected=422)
    p.login("collaborator")
    p.call("GET", f"/v1/schedules?professional_id={p.h.ids['other_professional']}", expected=404)


def test_schedule_permission_grant_and_exception_block_crud(portal):
    p = portal
    p.login()
    member_id = str(p.h.ids["collaborator_member"])
    p.call(
        "PATCH",
        f"/v1/team/memberships/{member_id}",
        p.command(
            version=0,
            role="collaborator",
            active=True,
            can_manage_schedule=True,
            professional_ids=[],
            queue_ids=[],
        ),
        expected=200,
    )
    p.login("collaborator")
    schedule = p.command(
        version=0,
        professional_id=str(p.h.ids["professional"]),
        unit_id=str(p.h.ids["unit"]),
        weekday=0,
        start_minute=600,
        end_minute=720,
        valid_from=p.h.start.date().isoformat(),
    )
    result = p.call("POST", "/v1/schedules", schedule, expected=200).json()
    p.call(
        "DELETE",
        f"/v1/schedules/{result['id']}",
        p.command(version=result["version"]),
        expected=200,
    )
    exception = p.call(
        "POST",
        "/v1/schedule-exceptions",
        p.command(
            version=0,
            professional_id=str(p.h.ids["professional"]),
            unit_id=str(p.h.ids["unit"]),
            day=p.h.start.date().isoformat(),
            closed=True,
        ),
        expected=200,
    ).json()
    p.call(
        "DELETE",
        f"/v1/schedule-exceptions/{exception['id']}",
        p.command(version=exception["version"]),
        expected=200,
    )
    block = p.call(
        "POST",
        "/v1/blocked-periods",
        p.command(
            version=0,
            professional_id=str(p.h.ids["professional"]),
            unit_id=str(p.h.ids["unit"]),
            starts_at=p.h.start.isoformat(),
            ends_at=(p.h.start + timedelta(hours=1)).isoformat(),
        ),
        expected=200,
    ).json()
    p.call(
        "DELETE",
        f"/v1/blocked-periods/{block['id']}",
        p.command(version=block["version"]),
        expected=200,
    )


def test_last_admin_and_csrf_idempotency_header_guards(portal):
    p = portal
    p.login()
    p.call(
        "PATCH",
        f"/v1/team/memberships/{p.h.ids['admin_member']}",
        p.command(
            version=0,
            role="collaborator",
            active=True,
            can_manage_schedule=False,
            professional_ids=[],
            queue_ids=[],
        ),
        expected=409,
    )
    body = service_body(p)
    assert (
        p.client.post(
            "/v1/services",
            json=body,
            headers={
                "Origin": p.h.settings.public_origin,
                "Idempotency-Key": body["idempotency_key"],
            },
        ).status_code
        == 403
    )
    assert p.client.post("/v1/services", json=body, headers=p.headers()).status_code == 422
    p.call("POST", "/v1/services", body | {"tenant_id": str(p.h.ids["other_tenant"])}, expected=422)


def test_recent_mfa_is_required_for_configuration(portal):
    p = portal
    p.login()
    with Session(p.h.admin) as db, db.begin():
        session = db.scalar(select(PortalSession))
        session.authenticated_at = datetime.now(UTC) - timedelta(minutes=20)
    p.call("POST", "/v1/services", service_body(p), expected=403)
    p.call("GET", "/v1/portal/catalog", expected=200)


def test_integration_write_only_cipher_and_secret_aware_idempotency(portal, caplog):
    p = portal
    p.login()
    caplog.set_level("INFO", logger="clinic.requests")
    secret = "synthetic-" + uuid4().hex  # pragma: allowlist secret (valor sintético de teste)
    body = p.command(version=0, credentials={"api_key": secret})
    result = p.call("PUT", "/v1/integrations/ai", body, expected=200).json()
    assert result["configured"] and result["verification_status"] == "not_verified"
    assert p.call("PUT", "/v1/integrations/ai", body, expected=200).json() == result
    p.call(
        "PUT",
        "/v1/integrations/ai",
        body
        | {
            "credentials": {"api_key": uuid4().hex}  # pragma: allowlist secret (valor sintético)
        },  # pragma: allowlist secret (valor sintético de teste)
        expected=409,
    )
    response = p.call("GET", "/v1/integrations", expected=200)
    assert (
        secret not in response.text
        and "credentials_ciphertext" not in response.text
        and secret not in caplog.text
    )
    with Session(p.h.admin) as db:
        row = db.scalar(select(IntegrationConfig))
        assert secret not in row.credentials_ciphertext
        assert secret in unseal(
            p.h.settings, p.h.ids["tenant"], "integration", row.id, "ai", row.credentials_ciphertext
        )
    p.login("reception")
    p.call(
        "PUT",
        "/v1/integrations/ai",
        p.command(version=1, credentials={"api_key": secret}),
        expected=403,
    )


def test_inbox_concurrent_claim_reply_idempotency_and_return_to_bot(portal):
    p = portal
    p.login()
    handoff = p.call(
        "POST",
        "/v1/handoffs",
        p.command(
            contact_id=str(p.h.ids["contact"]),
            queue_id=str(p.h.ids["queue"]),
            reason_code="patient_request",
        ),
        expected=200,
    ).json()
    p.login("reception")
    clients = []
    for role in ("admin", "reception"):
        client = TestClient(p.client.app, base_url="https://testserver")
        client.cookies.update(p.cookies[role])
        clients.append(client)
    barrier = Barrier(2)

    def claim(client):
        barrier.wait(timeout=10)
        body = p.command(version=0)
        return client.post(
            f"/v1/handoffs/{handoff['id']}/claim",
            json=body,
            headers={
                "Origin": p.h.settings.public_origin,
                "X-CSRF-Token": client.cookies.get("__Host-clinic_csrf"),
                "Idempotency-Key": body["idempotency_key"],
            },
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, clients))
    assert sorted(result.status_code for result in results) == [200, 409]
    winner = clients[next(i for i, result in enumerate(results) if result.status_code == 200)]
    p.client.cookies.clear()
    p.client.cookies.update(dict(winner.cookies))
    reply = p.command(version=1, text="Resposta sintética <img src=x onerror=alert(1)> 👋")
    result = p.call("POST", f"/v1/handoffs/{handoff['id']}/replies", reply, expected=200).json()
    assert result["delivery_status"] == "queued" and result["version"] == 2
    assert (
        p.call("POST", f"/v1/handoffs/{handoff['id']}/replies", reply, expected=200).json()
        == result
    )
    messages = p.call("GET", f"/v1/handoffs/{handoff['id']}/messages", expected=200).json()
    assert messages["items"][0]["text"] == reply["text"]
    p.call("POST", f"/v1/handoffs/{handoff['id']}/release", p.command(version=2), expected=200)
    with Session(p.h.admin) as db:
        assert db.scalar(select(ConversationState)).state == "MENU"
        assert db.scalar(select(func.count()).select_from(Message)) == 1
        row = db.scalar(select(Message))
        assert reply["text"] not in row.body_ciphertext
        assert db.scalar(select(func.count()).select_from(OutboxEvent)) == 1
    p.login("other_user")
    p.call("GET", f"/v1/handoffs/{handoff['id']}/messages", expected=404)
    for client in clients:
        client.close()


def test_queue_assignment_is_required_even_for_clinic_admin(portal):
    p = portal
    p.login()
    p.call(
        "POST",
        "/v1/handoffs",
        p.command(
            contact_id=str(p.h.ids["contact"]),
            queue_id=str(p.h.ids["foreign_queue"]),
            reason_code="financial",
        ),
        expected=404,
    )
    with Session(p.h.admin) as db, db.begin():
        db.execute(
            text("DELETE FROM queue_memberships WHERE membership_id=:id"),
            {"id": p.h.ids["admin_member"]},
        )
    assert p.call("GET", "/v1/inbox", expected=200).json()["items"] == []
    p.call(
        "POST",
        "/v1/handoffs",
        p.command(
            contact_id=str(p.h.ids["contact"]),
            queue_id=str(p.h.ids["queue"]),
            reason_code="patient_request",
        ),
        expected=404,
    )


def test_platform_management_is_separate_from_clinic_data(portal):
    p = portal
    p.login("superadmin")
    p.call("GET", "/v1/appointments?" + p.period(), expected=403)
    p.call("GET", "/v1/inbox", expected=403)
    p.call("GET", f"/v1/platform/break-glass/{uuid4()}/appointment", expected=404)
    p.call("POST", "/v1/platform/break-glass", {}, expected=404)
    users = p.call("GET", "/v1/platform/users?search=reception", expected=200).json()["items"]
    assert [user["login"] for user in users] == ["reception@test.invalid"]
    p.call("PATCH", f"/v1/platform/users/{users[0]['id']}", p.command(active=False), expected=200)
    assert not p.call("GET", "/v1/platform/users?search=reception", expected=200).json()["items"][
        0
    ]["active"]
    p.call("PATCH", f"/v1/platform/users/{users[0]['id']}", p.command(active=True), expected=200)
    p.login()
    p.call("GET", "/v1/platform/users", expected=403)


def test_platform_and_clinic_admin_manage_permissions_with_tenant_scope(portal):
    p = portal
    tenant = p.h.ids["tenant"]
    member = p.h.ids["reception_member"]
    path = f"/v1/platform/tenants/{tenant}/permissions"
    values = {
        "version": 0,
        "role": "reception",
        "active": True,
        "can_manage_schedule": True,
        "professional_ids": [str(p.h.ids["professional"])],
        "queue_ids": [str(p.h.ids["queue"])],
    }
    p.login()
    p.call("GET", path, expected=403)
    p.call("PATCH", f"{path}/{member}", p.command(**values), expected=403)
    p.call(
        "PATCH",
        f"/v1/team/memberships/{p.h.ids['other_member']}",
        p.command(**values),
        expected=404,
    )
    p.login("superadmin")
    page = p.call("GET", path, expected=200).json()
    assert str(member) in {row["id"] for row in page["items"]}
    assert str(p.h.ids["other_member"]) not in {row["id"] for row in page["items"]}
    assert {item["id"] for item in page["queues"]} == {str(p.h.ids["queue"])}
    p.call(
        "PATCH",
        f"{path}/{member}",
        p.command(**(values | {"queue_ids": [str(p.h.ids["foreign_queue"])]})),
        expected=404,
    )
    p.call("PATCH", f"{path}/{p.h.ids['other_member']}", p.command(**values), expected=404)
    command = p.command(**values)
    receipt = p.call("PATCH", f"{path}/{member}", command, expected=200).json()
    assert p.call("PATCH", f"{path}/{member}", command, expected=200).json() == receipt
    p.call("GET", "/v1/inbox", expected=403)
    p.login()
    members = p.call("GET", "/v1/team/memberships", expected=200).json()["items"]
    edited = next(item for item in members if item["id"] == str(member))
    assert edited["can_manage_schedule"] and edited["queue_ids"] == values["queue_ids"]
    p.call(
        "PATCH",
        f"/v1/team/memberships/{member}",
        p.command(**(values | {"version": receipt["version"], "role": "collaborator"})),
        expected=200,
    )


def test_platform_audit_and_deletions_are_scoped(portal):
    p = portal
    tenant = p.h.ids["tenant"]
    member = p.h.ids["reception_member"]
    p.login()
    p.call("GET", "/v1/platform/audit", expected=403)
    p.call(
        "DELETE",
        f"/v1/team/memberships/{p.h.ids['other_member']}",
        p.command(version=0),
        expected=404,
    )
    p.call(
        "DELETE",
        f"/v1/team/memberships/{p.h.ids['admin_member']}",
        p.command(version=0),
        expected=409,
    )
    command = p.command(version=0)
    p.call("DELETE", f"/v1/team/memberships/{member}", command, expected=200)
    p.call("DELETE", f"/v1/team/memberships/{member}", command, expected=200)
    assert str(member) not in {
        row["id"] for row in p.call("GET", "/v1/team/memberships", expected=200).json()["items"]
    }
    p.login("superadmin")
    p.call("GET", "/v1/platform/overview", expected=200)
    events = p.call(
        "GET", f"/v1/platform/audit?clinic={tenant}&action=membership.deleted", expected=200
    ).json()
    assert [event["resource_id"] for event in events["items"]] == [str(member)]
    p.call("DELETE", f"/v1/platform/users/{p.h.ids['reception']}", p.command(), expected=200)
    assert not p.call("GET", "/v1/platform/users?search=reception", expected=200).json()["items"]
    p.call("DELETE", f"/v1/platform/tenants/{tenant}", p.command(version=0), expected=200)
    assert str(tenant) not in {
        row["id"] for row in p.call("GET", "/v1/platform/tenants", expected=200).json()["items"]
    }
    p.login()
    p.call("GET", "/v1/portal/catalog", expected=401)


def test_platform_clinic_registration(portal):
    p = portal
    p.login("superadmin")
    body = {"name": "Clínica Teste", "timezone": "America/Fortaleza", "active": True, "version": 0}
    p.call("POST", "/v1/platform/tenants", p.command(**body), expected=422)
    registration = {
        "legal_name": "Clínica Teste Ltda",
        "document": "12.345.678/0001-90",
        "responsible_name": "Pessoa Responsável",
        "email": "contato@test.invalid",
        "phone": "85999990000",
        "postal_code": "60000-001",
        "address": "Rua Teste",
        "address_number": "100",
        "neighborhood": "Centro",
        "city": "Fortaleza",
        "state": "CE",
    }
    result = p.call(
        "POST", "/v1/platform/tenants", p.command(**body, registration=registration), expected=200
    ).json()
    clinics = p.call("GET", "/v1/platform/tenants", expected=200).json()["items"]
    row = next(clinic for clinic in clinics if clinic["id"] == result["id"])
    assert row["registration"]["document"] == registration["document"]


def test_platform_operator_registration_is_independent_of_membership_role(portal):
    p = portal
    p.login("superadmin")
    with Session(p.h.admin) as db, db.begin():
        db.delete(db.get(PlatformOperator, p.h.ids["superadmin"]))
    p.call("GET", "/v1/platform/tenants", expected=403)


def test_superadmin_invites_new_global_operator(portal):
    p = portal
    path = "/v1/platform/operators/invitations"
    login = "new-operator@test.invalid"
    command = p.command(login=login)
    p.call("POST", path, command, expected=401)
    p.login()
    p.call("POST", path, command, expected=403)
    p.login("superadmin")
    p.call("POST", path, p.command(login="admin@test.invalid"), expected=409)
    receipt = p.call("POST", path, command, expected=202).json()
    assert p.call("POST", path, command, expected=202).json() == receipt

    p.client.cookies.clear()
    setup = "/v1/auth/activate/setup"
    activation = {"login": login, "activation_code": receipt["activation_code"]}
    p.call("POST", setup, activation | {"login": "other@test.invalid"}, expected=409)
    key = p.call("POST", setup, activation, expected=200).json()["authenticator_key"]
    totp = pyotp.TOTP(key)
    credentials = activation | {
        "authenticator_key": key,
        "password": f"test-{uuid4().hex}",
        "profile": {"full_name": "Operador Convidado", "email": login, "phone": "85999990000"},
    }
    bad_code = "000000" if totp.now() != "000000" else "111111"
    p.call("POST", "/v1/auth/activate", credentials | {"code": bad_code}, expected=422)
    p.call("POST", "/v1/auth/activate", credentials | {"code": totp.now()}, expected=200)
    session = p.call("GET", "/v1/auth/session", expected=200).json()
    assert session["platform_access"] and session["memberships"] == []
    p.call("GET", "/v1/appointments?" + p.period(), expected=403)
    p.call("POST", setup, activation, expected=409)
    events = p.call("GET", "/v1/platform/audit?action=platform_operator.", expected=200).json()
    assert {(row["action"], row["resource_id"]) for row in events["items"]} == {
        ("platform_operator.invited", receipt["id"]),
        ("platform_operator.activated", receipt["id"]),
    }


def test_profile_details_and_photo_are_private(portal):
    p = portal
    p.login("reception")
    details = {
        "full_name": "Recepção Teste",
        "email": "recepcao@test.invalid",
        "phone": "85999990000",
    }
    p.call("PUT", "/v1/auth/profile", details, expected=204)
    p.call("PUT", "/v1/auth/profile/photo", {"jpeg": "invalid"}, expected=422)
    p.call("PUT", "/v1/auth/profile/photo", {"jpeg": "/9j//9k="}, expected=204)
    assert (
        p.call("GET", "/v1/auth/profile/photo", expected=200).headers["content-type"]
        == "image/jpeg"
    )
    own = p.call("GET", "/v1/auth/profile", expected=200).json()
    assert own["details"]["full_name"] == details["full_name"] and own["has_photo"]
    p.login()
    assert p.call("GET", "/v1/auth/profile", expected=200).json()["details"] is None
    p.call("GET", "/v1/auth/profile/photo", expected=404)
    p.login("superadmin")
    users = p.call("GET", "/v1/platform/users?search=Recepção Teste", expected=200).json()["items"]
    assert len(users) == 1 and users[0]["details"]["email"] == details["email"]
    assert "photo" not in users[0]
    p.login("reception")
    p.call("PUT", "/v1/auth/profile/photo", {"jpeg": None}, expected=204)
    p.call("GET", "/v1/auth/profile/photo", expected=404)


def test_invitation_requires_recipient_consent_and_does_not_enumerate_accounts(portal):
    p = portal
    p.login()
    known = p.call(
        "POST",
        "/v1/team/invitations",
        p.command(login="other_user@test.invalid", role="collaborator"),
        expected=202,
    ).json()
    unknown = p.call(
        "POST",
        "/v1/team/invitations",
        p.command(login="not-provisioned@test.invalid", role="collaborator"),
        expected=202,
    ).json()
    assert known.keys() == unknown.keys()
    assert {key: value for key, value in known.items() if key not in {"id", "activation_code"}} == {
        key: value for key, value in unknown.items() if key not in {"id", "activation_code"}
    }
    assert len(known["activation_code"]) == len(unknown["activation_code"])
    with Session(p.h.admin) as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(Membership)
                .where(
                    Membership.tenant_id == p.h.ids["tenant"],
                    Membership.user_id == p.h.ids["other_user"],
                )
            )
            == 0
        )
    p.login("other_user")
    assert (
        p.call("GET", "/v1/auth/invitations", expected=200).json()["items"][0]["id"] == known["id"]
    )
    result = p.call("POST", f"/v1/auth/invitations/{known['id']}/accept", {}, expected=200).json()
    assert (
        p.call("POST", f"/v1/auth/invitations/{known['id']}/accept", {}, expected=200).json()
        == result
    )
    session = p.call("GET", "/v1/auth/session", expected=200).json()
    assert result["membership_id"] in {member["id"] for member in session["memberships"]}


@pytest.mark.parametrize("issuer", ["admin", "superadmin"])
def test_invited_user_activates_in_portal_with_mfa(portal, issuer):
    p = portal
    p.login(issuer)
    login = "new-user@test.invalid"
    role = "reception" if issuer == "admin" else "admin"
    path = (
        "/v1/team/invitations"
        if issuer == "admin"
        else f"/v1/platform/tenants/{p.h.ids['tenant']}/administrators"
    )
    command = p.command(login=login, role=role)
    invitation = p.call("POST", path, command, expected=202).json()
    assert p.call("POST", path, command, expected=202).json() == invitation
    p.client.cookies.clear()
    activation = {"login": login, "activation_code": invitation["activation_code"]}
    setup = "/v1/auth/activate/setup"
    p.call("POST", setup, activation | {"login": "other@test.invalid"}, expected=409)
    key = p.call("POST", setup, activation, expected=200).json()["authenticator_key"]
    totp = pyotp.TOTP(key)
    bad_code = "000000" if totp.now() != "000000" else "111111"
    password = f"test-{uuid4().hex}"
    profile = {"full_name": "Pessoa Convidada", "email": login, "phone": "(85) 99999-0000"}
    credentials = activation | {"authenticator_key": key, "password": password, "profile": profile}
    p.call("POST", "/v1/auth/activate", credentials | {"code": bad_code}, expected=422)
    p.call("POST", "/v1/auth/activate", credentials | {"code": totp.now()}, expected=200)
    session = p.call("GET", "/v1/auth/session", expected=200).json()
    with Session(p.h.admin) as db:
        user = db.get(User, UUID(session["user_id"]))
        assert user is not None and user.login == login
    assert [(member["tenant_id"], member["role"]) for member in session["memberships"]] == [
        (str(p.h.ids["tenant"]), role)
    ]
    assert (
        p.call("GET", "/v1/auth/profile", expected=200).json()["details"]["full_name"]
        == profile["full_name"]
    )
    p.call("POST", setup, activation, expected=409)
