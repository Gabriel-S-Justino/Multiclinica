from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, insert, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from backend.application.scheduling import Scheduler
from backend.application.scheduling_commands import (
    AppointmentMutation,
    AvailabilityQuery,
    ConfirmRequest,
    ContactRequest,
    HoldRequest,
    NewPatient,
    ReleaseRequest,
    RescheduleRequest,
    TransitionRequest,
)
from backend.domain.permissions import Principal
from backend.domain.scheduling import SchedulingError
from backend.infrastructure.db import set_tenant
from backend.infrastructure.fields import seal, unseal
from backend.infrastructure.models import Resource, Unit
from backend.infrastructure.scheduling_models import (
    Appointment,
    AppointmentHold,
    AppointmentTransition,
    BlockedPeriod,
    BookingResource,
    Contact,
    ContactPatientLink,
    Conversation,
    ConversationState,
    Holiday,
    OutboxEvent,
    Patient,
    ProfessionalSchedule,
    ProfessionalService,
    ScheduleException,
    Service,
    ServiceResource,
)
from backend.infrastructure.security import digest


@dataclass
class Harness:
    settings: object
    admin: object
    runtime: object
    ids: dict
    start: datetime
    identity: Principal

    def run(self, method, command, identity=None):
        with Session(self.runtime) as db, db.begin():
            return getattr(Scheduler(db, self.settings, identity or self.identity), method)(command)

    def hold(self, **changes):
        values = dict(
            idempotency_key=uuid4().hex,
            service_id=self.ids["service"],
            unit_id=self.ids["unit"],
            contact_id=self.ids["contact"],
            professional_id=self.ids["professional"],
            starts_at=self.start,
        )
        return self.run("create_hold", HoldRequest(**(values | changes)))

    def confirm(self, hold, **changes):
        values = dict(
            idempotency_key=uuid4().hex,
            hold_id=UUID(hold["hold_id"]),
            contact_id=self.ids["contact"],
            patient_id=self.ids["patient"],
        )
        return self.run("confirm", ConfirmRequest(**(values | changes)))

    def query(self, **changes):
        day = self.start.astimezone(ZoneInfo("America/Sao_Paulo")).date()
        values = dict(
            service_id=self.ids["service"],
            unit_id=self.ids["unit"],
            professional_id=self.ids["professional"],
            first_date=day,
            last_date=day,
            limit=100,
        )
        return self.run("availability", AvailabilityQuery(**(values | changes)))


@pytest.fixture
def scheduling(foundation):
    settings, admin, ids, _, client = foundation
    ids = dict(ids) | {
        key: uuid4()
        for key in (
            "service",
            "unit",
            "foreign_unit",
            "resource",
            "contact",
            "patient",
            "conversation",
        )
    }
    now = datetime.now(UTC)
    day = (now.astimezone(ZoneInfo("America/Sao_Paulo")) + timedelta(days=1)).date()
    start = datetime.combine(day, datetime.min.time(), ZoneInfo("America/Sao_Paulo")).astimezone(
        UTC
    ) + timedelta(hours=10)
    with Session(admin) as db, db.begin():
        db.add_all(
            [
                Unit(id=ids["unit"], tenant_id=ids["tenant"], name="Unidade sintética"),
                Unit(id=ids["foreign_unit"], tenant_id=ids["other_tenant"], name="Unidade externa"),
            ]
        )
        service = Service(
            id=ids["service"],
            tenant_id=ids["tenant"],
            name="Serviço sintético",
            policy_validated=True,
            duration_minutes=30,
            step_minutes=15,
            buffer_before=0,
            buffer_after=0,
            min_notice_minutes=0,
            cancellation_notice_minutes=0,
            reschedule_notice_minutes=0,
            horizon_days=7,
            max_reschedules=2,
        )
        db.add(service)
        db.add(
            Contact(
                id=ids["contact"],
                tenant_id=ids["tenant"],
                phone_hash=digest(settings, f"contact:{ids['tenant']}", "+15550000000"),
                phone_ciphertext=seal(
                    settings, ids["tenant"], "contact", ids["contact"], "phone", "+15550000000"
                ),
            )
        )
        db.add(
            Patient(
                id=ids["patient"],
                tenant_id=ids["tenant"],
                name_ciphertext=seal(
                    settings, ids["tenant"], "patient", ids["patient"], "name", "Paciente sintético"
                ),
            )
        )
        db.flush()
        db.add(
            Resource(
                id=ids["resource"],
                tenant_id=ids["tenant"],
                unit_id=ids["unit"],
                name="Sala sintética",
            )
        )
        db.add(
            ContactPatientLink(
                tenant_id=ids["tenant"],
                contact_id=ids["contact"],
                patient_id=ids["patient"],
                relationship="self",
                verification_method="manual_clinic",
                verified_at=now,
                verified_until=now + timedelta(days=30),
                verified_by=ids["admin"],
            )
        )
        db.add(
            Conversation(id=ids["conversation"], tenant_id=ids["tenant"], contact_id=ids["contact"])
        )
        for professional in ("professional", "other_professional"):
            db.add(
                ProfessionalService(
                    tenant_id=ids["tenant"],
                    professional_id=ids[professional],
                    service_id=ids["service"],
                    active=True,
                )
            )
            for weekday in range(7):
                db.add(
                    ProfessionalSchedule(
                        tenant_id=ids["tenant"],
                        professional_id=ids[professional],
                        unit_id=ids["unit"],
                        weekday=weekday,
                        start_minute=540,
                        end_minute=1020,
                        valid_from=day - timedelta(days=10),
                    )
                )
        db.flush()
        db.add(
            ConversationState(
                tenant_id=ids["tenant"],
                conversation_id=ids["conversation"],
                state="SELECT_TIME",
                version=0,
                context={},
            )
        )
    return Harness(
        settings,
        admin,
        client.app.state.engine,
        ids,
        start,
        Principal(ids["admin"], ids["tenant"], ids["admin_member"], "admin", True),
    )


def test_availability_and_pagination(scheduling):
    h = scheduling
    page = h.query(limit=3)
    next_page = h.query(limit=3, offset=page.next_offset)
    assert len(page.items) == len(next_page.items) == 3
    assert {slot.start for slot in page.items}.isdisjoint(slot.start for slot in next_page.items)
    assert all(slot.end - slot.start == timedelta(minutes=30) for slot in page.items)
    assert (
        h.query(
            first_date=(h.start + timedelta(days=9)).date(),
            last_date=(h.start + timedelta(days=9)).date(),
        ).items
        == ()
    )


def test_unvalidated_policy_blocks_booking(scheduling):
    h = scheduling
    with Session(h.admin) as db, db.begin():
        db.get(Service, h.ids["service"]).policy_validated = False
    with pytest.raises(SchedulingError, match="service_unavailable"):
        h.hold()


def test_holiday_exception_and_block(scheduling):
    h = scheduling
    day = h.start.astimezone(ZoneInfo("America/Sao_Paulo")).date()
    with Session(h.admin) as db, db.begin():
        holiday = Holiday(tenant_id=h.ids["tenant"], day=day, unit_id=h.ids["unit"])
        db.add(holiday)
        db.flush()
        holiday_id = holiday.id
    assert not h.query().items
    with Session(h.admin) as db, db.begin():
        db.delete(db.get(Holiday, holiday_id))
        db.add(
            ScheduleException(
                tenant_id=h.ids["tenant"],
                professional_id=h.ids["professional"],
                unit_id=h.ids["unit"],
                day=day,
                closed=False,
                start_minute=600,
                end_minute=660,
            )
        )
        db.add(
            BlockedPeriod(
                tenant_id=h.ids["tenant"],
                professional_id=h.ids["professional"],
                starts_at=h.start,
                ends_at=h.start + timedelta(minutes=30),
            )
        )
    assert [item.start for item in h.query().items] == [h.start + timedelta(minutes=30)]


def test_fifty_simultaneous_holds_have_one_winner(scheduling):
    h, barrier = scheduling, Barrier(50)

    def attempt(_):
        barrier.wait(timeout=20)
        try:
            return h.hold()
        except SchedulingError as error:
            assert error.code in {"slot_unavailable", "booking_conflict"}
            return None

    with ThreadPoolExecutor(max_workers=50) as pool:
        results = list(pool.map(attempt, range(50)))
    assert sum(result is not None for result in results) == 1
    with Session(h.admin) as db:
        assert db.scalar(select(func.count()).select_from(AppointmentHold)) == 1


def test_fifty_simultaneous_confirmations_create_one_appointment(scheduling):
    h, barrier = scheduling, Barrier(50)
    hold = h.hold()

    def attempt(_):
        barrier.wait(timeout=20)
        try:
            return h.confirm(hold)
        except SchedulingError as error:
            assert error.code == "hold_unavailable"
            return None

    with ThreadPoolExecutor(max_workers=50) as pool:
        results = list(pool.map(attempt, range(50)))
    assert sum(result is not None for result in results) == 1
    with Session(h.admin) as db:
        assert db.scalar(select(func.count()).select_from(Appointment)) == 1
        assert db.scalar(select(func.count()).select_from(OutboxEvent)) == 1


def test_idempotency_replays_and_rejects_different_payload(scheduling):
    h = scheduling
    hold = h.hold(idempotency_key="repeat-hold-key")
    assert h.hold(idempotency_key="repeat-hold-key") == hold
    with pytest.raises(SchedulingError, match="idempotency_conflict"):
        h.hold(idempotency_key="repeat-hold-key", starts_at=h.start + timedelta(hours=1))
    result = h.confirm(hold, idempotency_key="repeat-confirm-key")
    assert h.confirm(hold, idempotency_key="repeat-confirm-key") == result


def test_shared_resource_blocks_other_professional_and_is_released(scheduling):
    h = scheduling
    hold = h.hold(resource_ids=[h.ids["resource"]])
    with pytest.raises(SchedulingError, match="slot_unavailable"):
        h.hold(professional_id=h.ids["other_professional"], resource_ids=[h.ids["resource"]])
    h.run(
        "release_hold",
        ReleaseRequest(
            idempotency_key=uuid4().hex, hold_id=UUID(hold["hold_id"]), contact_id=h.ids["contact"]
        ),
    )
    assert h.hold(professional_id=h.ids["other_professional"], resource_ids=[h.ids["resource"]])[
        "hold_id"
    ]


def test_mandatory_resource_cannot_be_omitted(scheduling):
    h = scheduling
    with Session(h.admin) as db, db.begin():
        db.add(
            ServiceResource(
                tenant_id=h.ids["tenant"],
                service_id=h.ids["service"],
                resource_id=h.ids["resource"],
            )
        )
    h.hold()
    with pytest.raises(SchedulingError, match="slot_unavailable"):
        h.hold(professional_id=h.ids["other_professional"])


def test_confirm_consumes_hold_and_atomically_finishes_conversation(scheduling):
    h = scheduling
    hold = h.hold(
        conversation_id=h.ids["conversation"],
        conversation_version=0,
        resource_ids=[h.ids["resource"]],
    )
    result = h.confirm(hold, conversation_version=hold["conversation_version"])
    with Session(h.admin) as db:
        assert db.get(AppointmentHold, UUID(hold["hold_id"])).state == "consumed"
        state = db.scalar(select(ConversationState))
        assert state.state == "DONE" and state.version == 2
        assert state.context == {"appointment_id": result["appointment_id"]}
        resource = db.scalar(select(BookingResource))
        assert resource.hold_id is None and str(resource.appointment_id) == result["appointment_id"]
        assert db.scalar(select(func.count()).select_from(AppointmentTransition)) == 1


def test_stale_conversation_rolls_back_patient_and_booking(scheduling):
    h = scheduling
    hold = h.hold(conversation_id=h.ids["conversation"], conversation_version=0)
    with pytest.raises(SchedulingError, match="conversation_conflict"):
        h.confirm(
            hold,
            patient_id=None,
            new_patient=NewPatient(
                display_name="Novo paciente sintético", purpose_acknowledged=True
            ),
            conversation_version=0,
        )
    with Session(h.admin) as db:
        assert db.scalar(select(func.count()).select_from(Patient)) == 1
        assert db.scalar(select(func.count()).select_from(Appointment)) == 0
        assert db.get(AppointmentHold, UUID(hold["hold_id"])).state == "held"


def test_new_patient_is_encrypted_and_not_automatically_verified(scheduling):
    h = scheduling
    result = h.confirm(
        h.hold(),
        patient_id=None,
        new_patient=NewPatient(display_name="Novo paciente sintético", purpose_acknowledged=True),
    )
    with Session(h.admin) as db:
        patient = db.get(Patient, UUID(result["patient_id"]))
        assert "Novo paciente" not in patient.name_ciphertext
        assert (
            unseal(
                h.settings, h.ids["tenant"], "patient", patient.id, "name", patient.name_ciphertext
            )
            == "Novo paciente sintético"
        )
        link = db.scalar(
            select(ContactPatientLink).where(ContactPatientLink.patient_id == patient.id)
        )
        assert link.verification_method is None
    with pytest.raises(SchedulingError, match="appointment_unavailable"):
        h.run(
            "cancel",
            AppointmentMutation(
                idempotency_key=uuid4().hex,
                appointment_id=UUID(result["appointment_id"]),
                contact_id=h.ids["contact"],
                version=0,
            ),
        )


def test_expired_hold_does_not_require_cleanup_job(scheduling):
    h = scheduling
    hold = h.hold()
    # Simulate elapsed time with a privileged test-only fixture; runtime cannot extend TTL.
    with Session(h.admin) as db, db.begin():
        db.execute(text("ALTER TABLE appointment_holds DISABLE TRIGGER booking_integrity"))
        db.execute(
            text("UPDATE appointment_holds SET expires_at=clock_timestamp()-interval '1 second'")
        )
        db.execute(text("ALTER TABLE appointment_holds ENABLE TRIGGER booking_integrity"))
    with pytest.raises(SchedulingError, match="hold_unavailable"):
        h.confirm(hold)
    assert h.hold()["hold_id"] != hold["hold_id"]


def test_hold_confirmation_revalidates_changed_schedule(scheduling):
    h = scheduling
    hold = h.hold()
    with Session(h.admin) as db, db.begin():
        db.add(
            BlockedPeriod(
                tenant_id=h.ids["tenant"],
                professional_id=h.ids["professional"],
                starts_at=h.start,
                ends_at=h.start + timedelta(hours=1),
            )
        )
    with pytest.raises(SchedulingError, match="hold_stale"):
        h.confirm(hold)


def test_overlapping_reschedule_is_atomic_and_transfers_resource(scheduling):
    h = scheduling
    original = h.confirm(h.hold(resource_ids=[h.ids["resource"]]))
    hold = h.hold(
        starts_at=h.start + timedelta(minutes=15),
        resource_ids=[h.ids["resource"]],
        reschedule_appointment_id=UUID(original["appointment_id"]),
        appointment_version=0,
    )
    result = h.run(
        "reschedule",
        RescheduleRequest(
            idempotency_key="reschedule-synthetic",
            appointment_id=UUID(original["appointment_id"]),
            contact_id=h.ids["contact"],
            version=0,
            hold_id=UUID(hold["hold_id"]),
        ),
    )
    with Session(h.admin) as db:
        old = db.get(Appointment, UUID(original["appointment_id"]))
        new = db.get(Appointment, UUID(result["appointment_id"]))
        assert old.status == "rescheduled" and old.replaced_by_id == new.id
        assert new.reschedule_count == 1 and new.starts_at == h.start + timedelta(minutes=15)
        assert db.scalar(select(func.count()).select_from(OutboxEvent)) == 3


def test_failed_reschedule_preserves_original(scheduling):
    h = scheduling
    original = h.confirm(h.hold())
    hold = h.hold(
        starts_at=h.start + timedelta(hours=1),
        reschedule_appointment_id=UUID(original["appointment_id"]),
        appointment_version=0,
    )
    with Session(h.admin) as db, db.begin():
        db.add(
            BlockedPeriod(
                tenant_id=h.ids["tenant"],
                professional_id=h.ids["professional"],
                starts_at=h.start + timedelta(hours=1),
                ends_at=h.start + timedelta(hours=2),
            )
        )
    with pytest.raises(SchedulingError, match="hold_stale"):
        h.run(
            "reschedule",
            RescheduleRequest(
                idempotency_key=uuid4().hex,
                appointment_id=UUID(original["appointment_id"]),
                contact_id=h.ids["contact"],
                version=0,
                hold_id=UUID(hold["hold_id"]),
            ),
        )
    with Session(h.admin) as db:
        assert db.get(Appointment, UUID(original["appointment_id"])).status == "scheduled"
        assert db.scalar(select(func.count()).select_from(Appointment)) == 1
        assert db.get(AppointmentHold, UUID(hold["hold_id"])).state == "held"


def test_cancel_releases_slot_and_terminal_transition_is_denied(scheduling):
    h = scheduling
    original = h.confirm(h.hold())
    command = AppointmentMutation(
        idempotency_key=uuid4().hex,
        appointment_id=UUID(original["appointment_id"]),
        contact_id=h.ids["contact"],
        version=0,
    )
    assert h.run("cancel", command)["status"] == "canceled"
    assert h.run("cancel", command)["version"] == 1
    assert h.hold()["hold_id"]
    with pytest.raises(SchedulingError, match="invalid_transition"):
        h.run(
            "transition",
            TransitionRequest(
                idempotency_key=uuid4().hex,
                appointment_id=command.appointment_id,
                contact_id=command.contact_id,
                version=1,
                target_status="confirmed",
            ),
        )


def test_least_future_load_uses_future_active_duration(scheduling):
    h = scheduling
    h.confirm(h.hold(starts_at=h.start + timedelta(hours=1)))
    result = h.hold(professional_id=None)
    assert result["professional_id"] == str(h.ids["other_professional"])
    assert result["strategy"] == "LeastFutureLoad/v1"


def test_least_future_load_does_not_penalize_completed_history(scheduling):
    h = scheduling
    historical_professional = min((h.ids["professional"], h.ids["other_professional"]), key=str)
    hold = h.hold(professional_id=historical_professional)
    h.run(
        "release_hold",
        ReleaseRequest(
            idempotency_key=uuid4().hex, hold_id=UUID(hold["hold_id"]), contact_id=h.ids["contact"]
        ),
    )
    with Session(h.admin) as db, db.begin():
        source = db.get(AppointmentHold, UUID(hold["hold_id"]))
        values = {
            column.name: getattr(source, column.name)
            for column in AppointmentHold.__table__.columns
            if column.computed is None and column.name not in {"id", "state"}
        }
        for key in ("starts_at", "ends_at", "occupied_start", "occupied_end", "expires_at"):
            values[key] -= timedelta(days=365)
        past_hold = AppointmentHold(**(values | {"id": uuid4(), "state": "consumed"}))
        db.add(past_hold)
        db.flush()
        past = Scheduler(db, h.settings, h.identity)._appointment_from_hold(
            past_hold, h.ids["patient"], uuid4()
        )
        db.add(past)
        db.flush()
        past.status, past.version = "completed", 1
    assert h.hold(professional_id=None)["professional_id"] == str(historical_professional)


def test_clinic_policy_limits_are_enforced_without_default_business_values(scheduling):
    h = scheduling
    original = h.confirm(h.hold())
    with Session(h.admin) as db, db.begin():
        policy = db.get(Service, h.ids["service"])
        policy.cancellation_notice_minutes = 3 * 24 * 60
        policy.max_reschedules = 0
    with pytest.raises(SchedulingError, match="cancellation_policy"):
        h.run(
            "cancel",
            AppointmentMutation(
                idempotency_key=uuid4().hex,
                appointment_id=UUID(original["appointment_id"]),
                contact_id=h.ids["contact"],
                version=0,
            ),
        )
    with pytest.raises(SchedulingError, match="reschedule_policy"):
        h.hold(
            starts_at=h.start + timedelta(hours=1),
            reschedule_appointment_id=UUID(original["appointment_id"]),
            appointment_version=0,
        )
    with Session(h.admin) as db, db.begin():
        db.get(Service, h.ids["service"]).min_notice_minutes = 3 * 24 * 60
    assert not h.query().items


def test_duration_override_and_buffers_change_eligible_slots(scheduling):
    h = scheduling
    with Session(h.admin) as db, db.begin():
        override = db.scalar(
            select(ProfessionalService).where(
                ProfessionalService.professional_id == h.ids["professional"]
            )
        )
        override.duration_minutes = 45
        policy = db.get(Service, h.ids["service"])
        policy.buffer_before, policy.buffer_after = 15, 15
    page = h.query()
    assert page.items[0].start == h.start - timedelta(
        minutes=45
    )  # opening 09:00 + 15 minute buffer
    assert all(item.end - item.start == timedelta(minutes=45) for item in page.items)
    h.hold()
    with pytest.raises(SchedulingError, match="slot_unavailable"):
        h.hold(starts_at=h.start + timedelta(minutes=45))


@pytest.mark.parametrize(
    "role,professional,allowed",
    [
        ("collaborator", "professional", True),
        ("collaborator", "other_professional", False),
        ("reception", "other_professional", False),
        ("superadmin", "professional", False),
    ],
)
def test_scheduling_professional_permissions(scheduling, role, professional, allowed):
    h = scheduling
    identity = Principal(h.ids[role], h.ids["tenant"], h.ids[f"{role}_member"], role, True)
    command = HoldRequest(
        idempotency_key=uuid4().hex,
        service_id=h.ids["service"],
        unit_id=h.ids["unit"],
        contact_id=h.ids["contact"],
        professional_id=h.ids[professional],
        starts_at=h.start,
    )
    if allowed:
        assert h.run("create_hold", command, identity)["hold_id"]
    else:
        with pytest.raises(SchedulingError):
            h.run("create_hold", command, identity)


def test_hold_owner_cannot_be_impersonated(scheduling):
    h = scheduling
    hold = h.hold()
    identity = Principal(
        h.ids["collaborator"], h.ids["tenant"], h.ids["collaborator_member"], "collaborator", True
    )
    with pytest.raises(SchedulingError, match="hold_unavailable"):
        h.run(
            "confirm",
            ConfirmRequest(
                idempotency_key=uuid4().hex,
                hold_id=UUID(hold["hold_id"]),
                contact_id=h.ids["contact"],
                patient_id=h.ids["patient"],
            ),
            identity,
        )


def test_application_boundary_requires_mfa_when_configured(scheduling):
    h = scheduling
    identity = Principal(h.ids["admin"], h.ids["tenant"], h.ids["admin_member"], "admin", False)
    with (
        pytest.raises(SchedulingError, match="permission_denied"),
        Session(h.runtime) as db,
        db.begin(),
    ):
        engine = Scheduler(db, h.settings.model_copy(update={"mfa_required": True}), identity)
        engine.availability(
            AvailabilityQuery(
                service_id=h.ids["service"],
                unit_id=h.ids["unit"],
                first_date=h.start.date(),
                last_date=h.start.date(),
            )
        )


def test_rls_idor_and_unverified_patient(scheduling):
    h = scheduling
    with pytest.raises(SchedulingError):
        h.hold(professional_id=h.ids["foreign_professional"])
    with pytest.raises(SchedulingError, match="unit_unavailable"):
        h.hold(unit_id=h.ids["foreign_unit"])
    hold = h.hold()
    with pytest.raises(SchedulingError, match="identity_unverified"):
        h.confirm(hold, patient_id=uuid4())
    forged = Principal(h.ids["admin"], h.ids["other_tenant"], h.ids["admin_member"], "admin", True)
    with pytest.raises(SchedulingError, match="permission_denied"):
        h.run(
            "availability",
            AvailabilityQuery(
                service_id=h.ids["service"],
                unit_id=h.ids["unit"],
                first_date=h.start.date(),
                last_date=h.start.date(),
            ),
            forged,
        )
    with Session(h.runtime) as db, db.begin():
        assert db.scalar(select(func.count()).select_from(AppointmentHold)) == 0
        assert db.scalar(select(func.count()).select_from(Patient)) == 0


def test_direct_sql_cannot_create_overlapping_hold_or_extend_ttl(scheduling):
    h = scheduling
    hold = h.hold()
    with Session(h.admin) as db:
        source = db.get(AppointmentHold, UUID(hold["hold_id"]))
        values = {
            column.name: getattr(source, column.name)
            for column in AppointmentHold.__table__.columns
            if column.computed is None and column.name != "id"
        }
    with pytest.raises(DBAPIError) as conflict, Session(h.runtime) as db, db.begin():
        set_tenant(db, h.ids["tenant"])
        db.execute(insert(AppointmentHold).values(**(values | {"id": uuid4()})))
    assert conflict.value.orig.sqlstate == "23P01"
    with pytest.raises(DBAPIError), Session(h.runtime) as db, db.begin():
        set_tenant(db, h.ids["tenant"])
        db.execute(
            text(
                "UPDATE appointment_holds SET expires_at=expires_at+interval '1 hour' WHERE id=:id"
            ),
            {"id": UUID(hold["hold_id"])},
        )


def test_register_contact_is_minimal_encrypted_and_idempotent(scheduling):
    h = scheduling
    command = ContactRequest(idempotency_key="contact-synthetic", phone="+15551112222")
    result = h.run("register_contact", command)
    assert h.run("register_contact", command) == result
    with Session(h.admin) as db:
        row = db.get(Contact, UUID(result["contact_id"]))
        assert command.phone not in row.phone_ciphertext
        assert (
            unseal(h.settings, h.ids["tenant"], "contact", row.id, "phone", row.phone_ciphertext)
            == command.phone
        )
    assert command.phone not in str(result)


def test_failure_after_booking_writes_rolls_back_every_effect(scheduling, monkeypatch):
    h = scheduling
    hold = h.hold(conversation_id=h.ids["conversation"], conversation_version=0)
    original_record = Scheduler._record

    def fail_after_record(self, *args, **kwargs):
        original_record(self, *args, **kwargs)
        self.db.flush()
        raise SchedulingError("injected_failure")

    monkeypatch.setattr(Scheduler, "_record", fail_after_record)
    with pytest.raises(SchedulingError, match="injected_failure"):
        h.confirm(
            hold,
            patient_id=None,
            new_patient=NewPatient(display_name="Paciente descartado", purpose_acknowledged=True),
            conversation_version=1,
        )
    with Session(h.admin) as db:
        assert db.scalar(select(func.count()).select_from(Patient)) == 1
        assert db.scalar(select(func.count()).select_from(Appointment)) == 0
        assert db.scalar(select(func.count()).select_from(OutboxEvent)) == 0
        assert db.scalar(select(func.count()).select_from(AppointmentTransition)) == 0
        assert db.get(AppointmentHold, UUID(hold["hold_id"])).state == "held"
        assert db.scalar(select(ConversationState)).state == "REVIEW"


def test_reschedule_failure_after_writes_preserves_old_and_hold(scheduling, monkeypatch):
    h = scheduling
    original = h.confirm(h.hold(resource_ids=[h.ids["resource"]]))
    hold = h.hold(
        starts_at=h.start + timedelta(minutes=15),
        reschedule_appointment_id=UUID(original["appointment_id"]),
        appointment_version=0,
        resource_ids=[h.ids["resource"]],
    )
    original_record = Scheduler._record

    def fail_after_record(self, *args, **kwargs):
        original_record(self, *args, **kwargs)
        self.db.flush()
        raise SchedulingError("injected_failure")

    monkeypatch.setattr(Scheduler, "_record", fail_after_record)
    with pytest.raises(SchedulingError, match="injected_failure"):
        h.run(
            "reschedule",
            RescheduleRequest(
                idempotency_key=uuid4().hex,
                appointment_id=UUID(original["appointment_id"]),
                contact_id=h.ids["contact"],
                version=0,
                hold_id=UUID(hold["hold_id"]),
            ),
        )
    with Session(h.admin) as db:
        old = db.get(Appointment, UUID(original["appointment_id"]))
        assert old.status == "scheduled" and old.replaced_by_id is None and old.version == 0
        assert db.scalar(select(func.count()).select_from(Appointment)) == 1
        assert db.scalar(select(func.count()).select_from(OutboxEvent)) == 1
        assert db.get(AppointmentHold, UUID(hold["hold_id"])).state == "held"


def test_cancellation_remains_possible_after_service_deactivation(scheduling):
    h = scheduling
    original = h.confirm(h.hold())
    with Session(h.admin) as db, db.begin():
        db.get(Service, h.ids["service"]).active = False
    assert (
        h.run(
            "cancel",
            AppointmentMutation(
                idempotency_key=uuid4().hex,
                appointment_id=UUID(original["appointment_id"]),
                contact_id=h.ids["contact"],
                version=0,
            ),
        )["status"]
        == "canceled"
    )


def test_runtime_sql_resource_overlap_is_rejected(scheduling):
    h = scheduling
    h.hold(resource_ids=[h.ids["resource"]])
    second = h.hold(professional_id=h.ids["other_professional"])
    with pytest.raises(DBAPIError) as conflict, Session(h.runtime) as db, db.begin():
        set_tenant(db, h.ids["tenant"])
        db.add(
            BookingResource(
                tenant_id=h.ids["tenant"],
                resource_id=h.ids["resource"],
                hold_id=UUID(second["hold_id"]),
            )
        )
        db.flush()
    assert conflict.value.orig.sqlstate == "23P01"


def test_fifty_direct_sql_inserts_are_serialized_by_database_trigger(scheduling):
    h = scheduling
    hold = h.hold()
    h.run(
        "release_hold",
        ReleaseRequest(
            idempotency_key=uuid4().hex, hold_id=UUID(hold["hold_id"]), contact_id=h.ids["contact"]
        ),
    )
    with Session(h.admin) as db:
        source = db.get(AppointmentHold, UUID(hold["hold_id"]))
        values = {
            column.name: getattr(source, column.name)
            for column in AppointmentHold.__table__.columns
            if column.computed is None and column.name not in {"id", "state"}
        }
    barrier = Barrier(50)

    def attempt(_):
        barrier.wait(timeout=20)
        try:
            with Session(h.runtime) as db, db.begin():
                set_tenant(db, h.ids["tenant"])
                db.execute(
                    insert(AppointmentHold).values(**(values | {"id": uuid4(), "state": "held"}))
                )
            return True
        except DBAPIError as error:
            assert error.orig.sqlstate == "23P01"
            return False

    with ThreadPoolExecutor(max_workers=50) as pool:
        assert sum(pool.map(attempt, range(50))) == 1
