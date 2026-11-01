from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from cryptography.exceptions import InvalidTag
from hypothesis import given
from hypothesis import settings as hypothesis_settings
from hypothesis import strategies as st
from pydantic import ValidationError

from backend.application.scheduling_commands import AvailabilityQuery, HoldRequest, NewPatient
from backend.domain.scheduling import (
    Interval,
    SchedulingError,
    candidate_slots,
    local_instant,
    validate_birth_date,
    validate_transition,
)
from backend.domain.selection import LeastFutureLoad, ProfessionalCandidate
from backend.infrastructure.fields import seal, unseal
from tests.unit.test_security import settings


@given(st.integers(0, 1000), st.integers(1, 100), st.integers(0, 1000), st.integers(1, 100))
def test_overlap_is_symmetric_and_half_open(a, a_duration, b, b_duration):
    origin = datetime(2026, 1, 1, tzinfo=UTC)
    first = Interval(origin + timedelta(minutes=a), origin + timedelta(minutes=a + a_duration))
    second = Interval(origin + timedelta(minutes=b), origin + timedelta(minutes=b + b_duration))
    assert first.overlaps(second) == second.overlaps(first)
    assert first.overlaps(second) == (a < b + b_duration and b < a + a_duration)


@hypothesis_settings(max_examples=100)
@given(
    duration=st.integers(1, 180),
    step=st.integers(1, 60),
    before=st.integers(0, 30),
    after=st.integers(0, 30),
    blocked_start=st.integers(540, 900),
    blocked_duration=st.integers(1, 60),
)
def test_slots_respect_duration_buffers_and_busy_intervals(
    duration, step, before, after, blocked_start, blocked_duration
):
    day, zone = date(2026, 10, 31), ZoneInfo("UTC")
    origin = datetime.combine(day, datetime.min.time(), UTC)
    busy = Interval(
        origin + timedelta(minutes=blocked_start),
        origin + timedelta(minutes=blocked_start + blocked_duration),
    )
    slots = candidate_slots(
        day,
        zone,
        [(540, 1020)],
        duration,
        step,
        before,
        after,
        [busy],
        origin,
        origin + timedelta(days=1),
    )
    assert slots == sorted(set(slots))
    for slot in slots:
        assert slot.end - slot.start == timedelta(minutes=duration)
        occupied = Interval(
            slot.start - timedelta(minutes=before), slot.end + timedelta(minutes=after)
        )
        assert not occupied.overlaps(busy)
        assert occupied.start >= origin + timedelta(minutes=540)
        assert occupied.end <= origin + timedelta(minutes=1020)


@pytest.mark.parametrize("day,minute", [(date(2026, 3, 8), 150), (date(2026, 11, 1), 90)])
def test_nonexistent_or_ambiguous_wall_time_is_not_offered(day, minute):
    assert local_instant(day, minute, ZoneInfo("America/New_York")) is None


def test_adjacent_appointments_are_not_conflicts():
    start = datetime(2026, 1, 1, tzinfo=UTC)
    assert not Interval(start, start + timedelta(minutes=30)).overlaps(
        Interval(start + timedelta(minutes=30), start + timedelta(hours=1))
    )


@pytest.mark.parametrize(
    "current,target",
    [
        ("completed", "scheduled"),
        ("canceled", "confirmed"),
        ("confirmed", "scheduled"),
        ("rescheduled", "completed"),
    ],
)
def test_terminal_or_backward_transition_is_denied(current, target):
    now = datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(SchedulingError, match="invalid_transition"):
        validate_transition(current, target, now, now)


def test_completion_before_start_is_denied():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(SchedulingError, match="appointment_not_started"):
        validate_transition("scheduled", "no_show", now + timedelta(days=1), now)


def test_encrypted_field_is_bound_to_tenant_row_and_field():
    config, tenant_id, row_id = settings(), uuid4(), uuid4()
    encrypted = seal(config, tenant_id, "patient", row_id, "name", "Paciente sintético")
    assert "Paciente" not in encrypted
    assert unseal(config, tenant_id, "patient", row_id, "name", encrypted) == "Paciente sintético"
    with pytest.raises(InvalidTag):
        unseal(config, uuid4(), "patient", row_id, "name", encrypted)
    with pytest.raises(InvalidTag):
        unseal(config, tenant_id, "patient", uuid4(), "name", encrypted)
    with pytest.raises(InvalidTag):
        unseal(config, tenant_id, "patient", row_id, "birth_date", encrypted)


def test_sensitive_commands_reject_free_tenant_and_naive_time():
    values = {
        "idempotency_key": "synthetic-key",
        "service_id": uuid4(),
        "unit_id": uuid4(),
        "contact_id": uuid4(),
        "starts_at": datetime(2026, 1, 1),
    }
    with pytest.raises((ValidationError, SchedulingError)):
        HoldRequest(**values)
    with pytest.raises(ValidationError):
        HoldRequest(
            **(values | {"starts_at": datetime(2026, 1, 1, tzinfo=UTC), "tenant_id": uuid4()})
        )
    with pytest.raises(ValidationError):
        NewPatient(display_name="  ", purpose_acknowledged=True)


def test_availability_window_is_bounded():
    with pytest.raises(ValidationError):
        AvailabilityQuery(
            service_id=uuid4(),
            unit_id=uuid4(),
            first_date=date(2026, 1, 1),
            last_date=date(2026, 3, 1),
        )


def test_least_future_load_orders_load_then_time_then_stable_id():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    one, two, three = UUID(int=1), UUID(int=2), UUID(int=3)
    rows = [
        ProfessionalCandidate(three, 60, now - timedelta(hours=1)),
        ProfessionalCandidate(two, 0, now),
        ProfessionalCandidate(one, 0, now),
    ]
    assert [row.professional_id for row in LeastFutureLoad().order(rows)] == [one, two, three]


def test_birth_date_uses_clinic_day_at_utc_midnight_boundary():
    now = datetime(2026, 11, 1, 1, tzinfo=UTC)
    zone = ZoneInfo("America/Sao_Paulo")
    validate_birth_date(date(2026, 10, 31), now, zone)
    with pytest.raises(SchedulingError, match="invalid_patient_data"):
        validate_birth_date(date(2026, 11, 1), now, zone)
