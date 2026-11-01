import hashlib
import hmac
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.application.messaging_worker import process_one, send_one
from backend.application.scheduling import Scheduler
from backend.application.scheduling_commands import HoldRequest, ReleaseRequest
from backend.domain.permissions import ContactPrincipal
from backend.domain.scheduling import SchedulingError
from backend.infrastructure.fields import seal, unseal
from backend.infrastructure.messaging_models import (
    Dispatch,
    InboundJob,
    MessagingChannel,
    MessagingSession,
)
from backend.infrastructure.models import Membership, Unit, User
from backend.infrastructure.portal_models import IntegrationConfig, Message, ServiceQueue
from backend.infrastructure.scheduling_models import (
    Appointment,
    ContactPatientLink,
    ConversationState,
)
from backend.infrastructure.whatsapp import ProviderFailure
from tests.integration.test_scheduling import scheduling  # noqa: F401


class MessagingHarness:
    def __init__(self, h, client, channel_id, secret):
        self.h, self.client, self.channel_id, self.secret = h, client, channel_id, secret

    def envelope(self, content="oi", *, event_id=None, timestamp=None, kind="text"):
        return {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "200",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {"phone_number_id": "100"},
                                "messages": [
                                    {
                                        "id": event_id or str(uuid4()),
                                        "from": "15550000000",
                                        "timestamp": str(
                                            timestamp or int(datetime.now(UTC).timestamp())
                                        ),
                                        "type": kind,
                                        "text": {"body": content},
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }

    def post(self, payload, *, signature=None):
        raw = json.dumps(payload).encode()
        header = (
            signature
            if signature is not None
            else "sha256=" + hmac.new(self.secret.encode(), raw, hashlib.sha256).hexdigest()
        )
        return self.client.post(
            f"/v1/webhooks/whatsapp/{self.channel_id}",
            content=raw,
            headers={"X-Hub-Signature-256": header, "Content-Type": "application/json"},
        )

    def step(self, text, **kwargs):
        response = self.post(self.envelope(text, **kwargs))
        assert response.status_code == 200, response.text
        assert process_one(self.h.runtime, self.h.settings, self.channel_id)
        with Session(self.h.admin) as db:
            jobs = list(db.scalars(select(InboundJob).order_by(InboundJob.sequence)))
            assert jobs[-1].status == "done", jobs[-1].error_code
        return self.context()

    def context(self):
        with Session(self.h.admin) as db:
            session = db.scalar(
                select(MessagingSession).where(MessagingSession.channel_id == self.channel_id)
            )
            state = db.scalar(
                select(ConversationState).where(
                    ConversationState.conversation_id == session.conversation_id
                )
            )
            context = json.loads(
                unseal(
                    self.h.settings,
                    session.tenant_id,
                    "messaging_session",
                    session.id,
                    "context",
                    session.context_ciphertext,
                )
            )
            return state.state, context

    def option(self, **wanted):
        _, context = self.context()
        return next(
            key
            for key, value in context["options"].items()
            if all(value.get(field) == expected for field, expected in wanted.items())
        )

    def any_option(self):
        return next(iter(self.context()[1]["options"]))

    def book_to_review(self):
        self.step("menu")
        self.step(self.option(action="book"))
        self.step(self.option(service_id=str(self.h.ids["service"])))
        self.step(self.option(unit_id=str(self.h.ids["unit"])))
        self.step(self.option(professional_id=str(self.h.ids["professional"])))
        self.step(self.any_option())
        self.step(self.any_option())
        self.step(self.option(purpose=True))
        self.step("Paciente de teste WhatsApp")
        assert self.context()[0] == "REVIEW"


@pytest.fixture
def messaging(foundation, request, synthetic_password_hash):
    h = request.getfixturevalue("scheduling")
    client = foundation[-1]
    actor, member, channel_id, queue_id, integration_id = [uuid4() for _ in range(5)]
    secret = uuid4().hex + uuid4().hex
    with Session(h.admin) as db, db.begin():
        db.add(
            User(
                id=actor,
                login=f"worker-{actor}@internal.invalid",
                password_hash=synthetic_password_hash,
                is_service=True,
                active=True,
            )
        )
        db.flush()
        db.add(
            Membership(
                id=member, tenant_id=h.ids["tenant"], user_id=actor, role="messaging", active=True
            )
        )
        db.add(
            ServiceQueue(
                id=queue_id,
                tenant_id=h.ids["tenant"],
                name="Fila de teste",
                kind="general",
                active=True,
                hours=[],
                outside_hours_notice="Solicitação registrada para o próximo expediente.",
            )
        )
        db.flush()
        db.add(
            MessagingChannel(
                id=channel_id,
                tenant_id=h.ids["tenant"],
                phone_number_id="100",
                account_id="200",
                actor_user_id=actor,
                actor_membership_id=member,
                default_queue_id=queue_id,
                active=True,
                send_enabled=False,
            )
        )
        db.add(
            IntegrationConfig(
                id=integration_id,
                tenant_id=h.ids["tenant"],
                provider="whatsapp",
                credentials_ciphertext=seal(
                    h.settings,
                    h.ids["tenant"],
                    "integration",
                    integration_id,
                    "whatsapp",
                    json.dumps(
                        {"app_secret": secret, "verify_token": secret, "access_token": secret}
                    ),
                ),
                version=1,
                updated_at=datetime.now(UTC),
            )
        )
    return MessagingHarness(h, client, channel_id, secret)


def test_webhook_auth_before_parse_routing_and_persistent_dedup(messaging):
    p = messaging
    assert p.post({"bad": "payload"}, signature="sha256=invalid").status_code == 401
    assert p.post({"bad": "payload"}).status_code == 400
    envelope = p.envelope()
    for _ in range(3):
        assert p.post(envelope).status_code == 200
    envelope["entry"][0]["id"] = "foreign"
    assert p.post(envelope).status_code == 400
    with Session(p.h.admin) as db:
        assert db.scalar(select(func.count()).select_from(InboundJob)) == 1
    url = f"/v1/webhooks/whatsapp/{p.channel_id}"
    assert (
        p.client.get(
            url,
            params={"hub.mode": "subscribe", "hub.verify_token": p.secret, "hub.challenge": "123"},
        ).text
        == "123"
    )
    assert (
        p.client.get(
            url, params={"hub.mode": "subscribe", "hub.verify_token": "bad", "hub.challenge": "123"}
        ).status_code
        == 403
    )


def test_whatsapp_real_domain_booking_and_duplicate_confirmation(messaging):
    p = messaging
    p.book_to_review()
    code = p.option(confirm=True)
    payload = p.envelope(code)
    for _ in range(2):
        assert p.post(payload).status_code == 200
    assert process_one(p.h.runtime, p.h.settings, p.channel_id)
    assert not process_one(p.h.runtime, p.h.settings, p.channel_id)
    assert p.context()[0] == "DONE"
    with Session(p.h.admin) as db:
        assert db.scalar(select(func.count()).select_from(Appointment)) == 1
        assert "Paciente de teste WhatsApp" not in " ".join(
            db.scalars(select(Message.body_ciphertext))
        )
        assert db.scalar(select(ConversationState.context)) == {}


def test_old_option_and_out_of_order_message_cannot_book(messaging):
    p = messaging
    p.step("menu")
    old = p.option(action="book")
    p.step("menu")
    assert p.step(old)[0] == "MENU"
    assert (
        p.step(p.option(action="book"), timestamp=int(datetime.now(UTC).timestamp()) - 100)[0]
        == "MENU"
    )
    with Session(p.h.admin) as db:
        assert db.scalar(select(func.count()).select_from(Appointment)) == 0


def test_handoff_silence_media_and_opt_out(messaging):
    p = messaging
    p.step("oi", kind="image")
    p.step("humano")
    with Session(p.h.admin) as db:
        before = db.scalar(select(func.count()).select_from(Dispatch))
    p.step("menu")
    p.step("", kind="image")
    assert p.context()[0] == "HUMAN_HANDOFF"
    with Session(p.h.admin) as db:
        assert db.scalar(select(func.count()).select_from(Dispatch)) == before
    p.step("parar")
    with Session(p.h.admin) as db:
        assert db.scalar(select(MessagingSession.opted_out))


def test_contact_worker_identity_cannot_release_other_contacts_hold(messaging):
    p = messaging
    p.step("menu")
    hold = p.h.hold()
    with Session(p.h.admin) as db:
        channel = db.get(MessagingChannel, p.channel_id)
        identity = ContactPrincipal(
            user_id=channel.actor_user_id,
            tenant_id=channel.tenant_id,
            membership_id=channel.actor_membership_id,
            role="messaging",
            mfa_verified=False,
            channel_id=channel.id,
            contact_id=uuid4(),
        )
    with Session(p.h.runtime) as db, db.begin(), pytest.raises(SchedulingError):
        Scheduler(db, p.h.settings, identity).release_hold(
            ReleaseRequest(
                idempotency_key=uuid4().hex,
                hold_id=UUID(hold["hold_id"]),
                contact_id=p.h.ids["contact"],
            )
        )


class FakeProvider:
    def __init__(self, failure=None):
        self.calls = 0
        self.failure = failure

    def send_text(self, destination, text):
        self.calls += 1
        if self.failure:
            raise self.failure
        return f"wamid-{uuid4()}"


@pytest.mark.parametrize("mode", ["success", "ambiguous", "closed_window", "opted_out", "disabled"])
def test_outbox_window_consent_and_unknown_no_resend(messaging, mode):
    p = messaging
    p.step("menu")
    with Session(p.h.admin) as db, db.begin():
        db.get(MessagingChannel, p.channel_id).send_enabled = mode != "disabled"
        session = db.scalar(select(MessagingSession))
        if mode == "closed_window":
            session.last_inbound_at = datetime.now(UTC) - timedelta(hours=25)
        if mode == "opted_out":
            session.opted_out = True
    provider = FakeProvider(
        ProviderFailure("delivery_unknown", ambiguous=True) if mode == "ambiguous" else None
    )
    send_one(p.h.runtime, p.h.settings, p.channel_id, provider)
    expected = (
        "sent"
        if mode == "success"
        else "unknown"
        if mode == "ambiguous"
        else "pending"
        if mode == "disabled"
        else "blocked"
    )
    with Session(p.h.admin) as db:
        assert db.scalar(select(Dispatch.status)) == expected
    send_one(p.h.runtime, p.h.settings, p.channel_id, provider)
    assert provider.calls == (1 if mode in {"success", "ambiguous"} else 0)


def test_parallel_ingest_and_process_has_one_effect(messaging):
    p = messaging
    payload = p.envelope()
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: p.post(payload).status_code, range(10)))
    assert results == [200] * 10
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(lambda _: process_one(p.h.runtime, p.h.settings, p.channel_id), range(10))
        )
    assert sum(results) == 1
    with Session(p.h.admin) as db:
        assert db.scalar(select(func.count()).select_from(Dispatch)) == 1


@pytest.mark.parametrize("action", ["cancel", "reschedule"])
def test_verified_contact_manages_appointment_via_explicit_options(messaging, action):
    p = messaging
    p.book_to_review()
    p.step(p.option(confirm=True))
    with Session(p.h.admin) as db, db.begin():
        row = db.scalar(select(Appointment))
        link = db.scalar(
            select(ContactPatientLink).where(ContactPatientLink.patient_id == row.patient_id)
        )
        link.verification_method = "manual_clinic"
        link.verified_by = p.h.ids["admin"]
        link.verified_at = datetime.now(UTC) - timedelta(minutes=1)
        link.verified_until = datetime.now(UTC) + timedelta(hours=1)
    p.step("menu")
    p.step(p.option(action="manage"))
    assert p.context()[0] == "APPOINTMENT"
    p.step(p.any_option())
    p.step(p.option(action=action))
    if action == "reschedule":
        p.step(p.any_option())
        p.step(p.any_option())
        assert p.context()[0] == "REVIEW"
    p.step(p.option(confirm=True))
    assert p.context()[0] == "DONE"
    with Session(p.h.admin) as db:
        states = list(db.scalars(select(Appointment.status)))
        assert (
            states == ["canceled"]
            if action == "cancel"
            else sorted(states) == ["rescheduled", "scheduled"]
        )


def test_delivery_callbacks_do_not_regress_read_state(messaging):
    p = messaging
    p.step("menu")
    with Session(p.h.admin) as db, db.begin():
        db.get(MessagingChannel, p.channel_id).send_enabled = True
    send_one(p.h.runtime, p.h.settings, p.channel_id, FakeProvider())
    with Session(p.h.admin) as db:
        provider_id = db.scalar(select(Dispatch.provider_id))
    for status in ["read", "delivered", "sent", "failed"]:
        payload = p.envelope()
        value = payload["entry"][0]["changes"][0]["value"]
        value.pop("messages")
        value["statuses"] = [{"id": provider_id, "status": status}]
        assert p.post(payload).status_code == 200
        assert process_one(p.h.runtime, p.h.settings, p.channel_id)
    with Session(p.h.admin) as db:
        assert db.scalar(select(Dispatch.status)) == "read"


def test_manual_identity_is_required_without_enumeration(messaging):
    p = messaging
    p.step("menu")
    p.step(p.option(action="manage"))
    with Session(p.h.admin) as db:
        before = list(
            db.scalars(select(Message.body_ciphertext).where(Message.direction == "outbound"))
        )
        assert len(before) == 2
        assert not p.context()[1].get("appointment_id")


def test_inactivity_reconfirms_and_expired_hold_does_not_confirm(messaging):
    p = messaging
    p.book_to_review()
    with Session(p.h.admin) as db, db.begin():
        session = db.scalar(select(MessagingSession))
        session.last_processed_at = datetime.now(UTC) - timedelta(hours=1)
    p.step(p.option(confirm=True))
    assert p.context()[0] == "RESUME"
    with Session(p.h.admin) as db:
        assert db.scalar(select(func.count()).select_from(Appointment)) == 0


def test_webhook_load_sample_durable_ack(messaging, record_property):
    p = messaging

    def request(_):
        started = time.perf_counter()
        response = p.post(p.envelope())
        return response.status_code, (time.perf_counter() - started) * 1000

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(request, range(100)))
    assert all(status == 200 for status, _ in results)
    timings = sorted(duration for _, duration in results)
    record_property("webhook_local_requests", 100)
    record_property("webhook_local_workers", 10)
    record_property("webhook_local_p95_ms", round(timings[94], 2))
    record_property("webhook_local_max_ms", round(timings[-1], 2))
    with Session(p.h.admin) as db:
        assert db.scalar(select(func.count()).select_from(InboundJob)) == 100


def test_idempotency_receipt_is_bound_to_contact_before_replay(messaging):
    p = messaging
    p.step("menu")
    with Session(p.h.admin) as db:
        channel = db.get(MessagingChannel, p.channel_id)
        identity = ContactPrincipal(
            user_id=channel.actor_user_id,
            tenant_id=channel.tenant_id,
            membership_id=channel.actor_membership_id,
            role="messaging",
            mfa_verified=False,
            channel_id=channel.id,
            contact_id=p.h.ids["contact"],
        )
    command = HoldRequest(
        idempotency_key=uuid4().hex,
        service_id=p.h.ids["service"],
        unit_id=p.h.ids["unit"],
        contact_id=p.h.ids["contact"],
        professional_id=p.h.ids["professional"],
        starts_at=p.h.start,
    )
    with Session(p.h.runtime) as db, db.begin():
        receipt = Scheduler(db, p.h.settings, identity).create_hold(command)
    from dataclasses import replace

    forged = replace(identity, contact_id=uuid4())
    with (
        Session(p.h.runtime) as db,
        db.begin(),
        pytest.raises(SchedulingError, match="identity_unverified"),
    ):
        Scheduler(db, p.h.settings, forged).create_hold(command)
    assert receipt["hold_id"]


def test_revoked_service_actor_cannot_read_patient_flow(messaging):
    p = messaging
    p.step("menu")
    with Session(p.h.admin) as db, db.begin():
        channel = db.get(MessagingChannel, p.channel_id)
        db.get(User, channel.actor_user_id).active = False
        before = db.scalar(select(func.count()).select_from(Dispatch))
    assert p.post(p.envelope("menu")).status_code == 200
    assert process_one(p.h.runtime, p.h.settings, p.channel_id)
    with Session(p.h.admin) as db:
        assert db.scalar(select(func.count()).select_from(Dispatch)) == before
        job = db.scalar(select(InboundJob).order_by(InboundJob.sequence.desc()).limit(1))
        assert job.status == "pending" and job.error_code == "permission_denied"


def test_unit_menu_is_bounded_and_paginated(messaging):
    p = messaging
    with Session(p.h.admin) as db, db.begin():
        db.add_all(
            Unit(tenant_id=p.h.ids["tenant"], name=f"Unidade sintética {index}")
            for index in range(15)
        )
    p.step("menu")
    p.step(p.option(action="book"))
    p.step(p.option(service_id=str(p.h.ids["service"])))
    first = p.context()[1]["options"]
    assert len(first) == 9
    assert p.step(p.option(offset=8))[0] == "UNIT"
    assert len(p.context()[1]["options"]) == 8
