from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo


class SchedulingError(Exception):
    def __init__(self, code: str = "booking_conflict") -> None:
        self.code = code
        super().__init__(code)


class AppointmentStatus(StrEnum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELED = "canceled"
    NO_SHOW = "no_show"
    RESCHEDULED = "rescheduled"


ACTIVE_STATUSES = (AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED)
TRANSITIONS = {
    AppointmentStatus.SCHEDULED: frozenset(AppointmentStatus) - {AppointmentStatus.SCHEDULED},
    AppointmentStatus.CONFIRMED: frozenset(
        {
            AppointmentStatus.COMPLETED,
            AppointmentStatus.CANCELED,
            AppointmentStatus.NO_SHOW,
            AppointmentStatus.RESCHEDULED,
        }
    ),
}


def validate_transition(current: str, target: str, starts_at: datetime, now: datetime) -> None:
    try:
        source, destination = AppointmentStatus(current), AppointmentStatus(target)
    except ValueError as error:
        raise SchedulingError("invalid_transition") from error
    if destination not in TRANSITIONS.get(source, frozenset()):
        raise SchedulingError("invalid_transition")
    if destination in {AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW} and now < starts_at:
        raise SchedulingError("appointment_not_started")


def utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise SchedulingError("timezone_required")
    return value.astimezone(UTC)


def validate_birth_date(value: date | None, now: datetime, zone: ZoneInfo) -> None:
    if value is not None and value > utc(now).astimezone(zone).date():
        raise SchedulingError("invalid_patient_data")


@dataclass(frozen=True, order=True)
class Interval:
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if utc(self.start) >= utc(self.end):
            raise SchedulingError("invalid_interval")

    def overlaps(self, other: "Interval") -> bool:
        return utc(self.start) < utc(other.end) and utc(other.start) < utc(self.end)

    def contains(self, other: "Interval") -> bool:
        return utc(self.start) <= utc(other.start) and utc(other.end) <= utc(self.end)


def local_instant(day: date, minute: int, zone: ZoneInfo) -> datetime | None:
    naive = datetime.combine(day, time()) + timedelta(minutes=minute)
    candidates = set()
    for fold in (0, 1):
        aware = naive.replace(tzinfo=zone, fold=fold)
        candidate = aware.astimezone(UTC)
        if candidate.astimezone(zone).replace(tzinfo=None) == naive:
            candidates.add(candidate)
    # Fail closed for both nonexistent and ambiguous local times.
    return next(iter(candidates)) if len(candidates) == 1 else None


def candidate_slots(
    day: date,
    zone: ZoneInfo,
    windows: list[tuple[int, int]],
    duration: int,
    step: int,
    before: int,
    after: int,
    busy: list[Interval],
    earliest: datetime,
    latest: datetime,
) -> list[Interval]:
    if duration <= 0 or step <= 0 or before < 0 or after < 0:
        raise SchedulingError("invalid_policy")
    result: set[Interval] = set()
    for opening, closing in windows:
        begin, finish = local_instant(day, opening, zone), local_instant(day, closing, zone)
        if begin is None or finish is None:
            continue
        window = Interval(begin, finish)
        for minute in range(opening, closing, step):
            start = local_instant(day, minute, zone)
            if start is None or start < utc(earliest) or start > utc(latest):
                continue
            slot = Interval(start, start + timedelta(minutes=duration))
            # Do not traverse a clock transition: only unambiguous local appointments.
            local_end = local_instant(day, minute + duration, zone)
            if local_end is None or local_end != slot.end:
                continue
            occupied = Interval(
                start - timedelta(minutes=before), slot.end + timedelta(minutes=after)
            )
            if window.contains(occupied) and not any(occupied.overlaps(item) for item in busy):
                result.add(slot)
    return sorted(result)
