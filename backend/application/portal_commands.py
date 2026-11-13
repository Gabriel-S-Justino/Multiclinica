from datetime import date, datetime
from typing import Literal, Self
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator, model_validator

from backend.application.contracts import Command
from backend.application.identity_details import ClinicDetails
from backend.application.scheduling_commands import Mutation
from backend.domain.scheduling import utc


class Versioned(Mutation):
    version: int = Field(ge=0)


class ServiceDraft(Versioned):
    name: str = Field(min_length=1, max_length=120)
    display_order: int = Field(ge=0, le=10000)
    active: bool
    requires_professional: bool
    policy_validated: bool = False
    requires_birth_date: bool = False
    duration_minutes: int | None = Field(default=None, ge=1, le=720)
    step_minutes: int | None = Field(default=None, ge=1, le=720)
    buffer_before: int | None = Field(default=None, ge=0, le=240)
    buffer_after: int | None = Field(default=None, ge=0, le=240)
    min_notice_minutes: int | None = Field(default=None, ge=0, le=525600)
    cancellation_notice_minutes: int | None = Field(default=None, ge=0, le=525600)
    reschedule_notice_minutes: int | None = Field(default=None, ge=0, le=525600)
    horizon_days: int | None = Field(default=None, ge=1, le=365)
    max_reschedules: int | None = Field(default=None, ge=0, le=100)
    hold_ttl_minutes: int | None = Field(default=None, ge=1, le=60)
    service_queue_id: UUID | None = None
    required_resource_ids: list[UUID] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def scheduling_parameters(self) -> Self:
        neutral = {
            "duration_minutes": 1,
            "step_minutes": 1,
            "buffer_before": 0,
            "buffer_after": 0,
            "min_notice_minutes": 0,
            "cancellation_notice_minutes": 0,
            "reschedule_notice_minutes": 0,
            "horizon_days": 1,
            "max_reschedules": 0,
            "hold_ttl_minutes": 10,
        }
        if self.requires_professional:
            if any(getattr(self, name) is None for name in neutral):
                raise ValueError("Defina todos os parâmetros clínicos explicitamente")
        else:
            if (
                self.requires_birth_date
                or self.required_resource_ids
                or (self.active and self.service_queue_id is None)
            ):
                raise ValueError("Serviço sem agenda exige fila e não coleta dados de paciente")
            self.policy_validated = False
            # Unused storage fields satisfy the legacy non-null schema; not clinical defaults.
            for name, value in neutral.items():
                setattr(self, name, value)
        return self

    @field_validator("name")
    @classmethod
    def nonblank(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Nome obrigatório")
        return value


class ProfessionalDraft(Versioned):
    display_name: str = Field(min_length=1, max_length=120)
    user_id: UUID | None = None
    active: bool
    service_ids: list[UUID] = Field(max_length=100)


class ScheduleDraft(Versioned):
    professional_id: UUID
    unit_id: UUID
    weekday: int = Field(ge=0, le=6)
    start_minute: int = Field(ge=0, le=1439)
    end_minute: int = Field(ge=1, le=1440)
    valid_from: date
    valid_until: date | None = None

    @model_validator(mode="after")
    def interval(self) -> Self:
        if self.end_minute <= self.start_minute or (
            self.valid_until and self.valid_until < self.valid_from
        ):
            raise ValueError("Intervalo inválido")
        return self


class ExceptionDraft(Versioned):
    professional_id: UUID
    unit_id: UUID
    day: date
    closed: bool
    start_minute: int | None = Field(default=None, ge=0, le=1439)
    end_minute: int | None = Field(default=None, ge=1, le=1440)

    @model_validator(mode="after")
    def interval(self) -> Self:
        if self.closed:
            if self.start_minute is not None or self.end_minute is not None:
                raise ValueError("Fechamento não aceita horário")
        elif (
            self.start_minute is None
            or self.end_minute is None
            or self.end_minute <= self.start_minute
        ):
            raise ValueError("Intervalo obrigatório")
        return self


class BlockDraft(Versioned):
    professional_id: UUID
    unit_id: UUID
    starts_at: datetime
    ends_at: datetime

    @field_validator("starts_at", "ends_at")
    @classmethod
    def normalize(cls, value: datetime) -> datetime:
        return utc(value)

    @model_validator(mode="after")
    def interval(self) -> Self:
        if not timedelta_in_range(self.starts_at, self.ends_at, 31):
            raise ValueError("Intervalo inválido ou maior que 31 dias")
        return self


def timedelta_in_range(start: datetime, end: datetime, days: int) -> bool:
    return 0 < (end - start).total_seconds() <= days * 86400


class UnitDraft(Versioned):
    name: str = Field(min_length=1, max_length=120)
    active: bool


class ResourceDraft(UnitDraft):
    unit_id: UUID


class InvitationDraft(Mutation):
    login: str = Field(min_length=3, max_length=254)
    role: Literal["collaborator", "reception", "admin"]


class MembershipDraft(Versioned):
    role: Literal["collaborator", "reception", "admin"]
    active: bool
    can_manage_schedule: bool
    professional_ids: list[UUID] = Field(max_length=100)
    queue_ids: list[UUID] = Field(max_length=100)


class ClinicPolicyDraft(Versioned):
    identity_policy_approved: bool
    identity_policy_reference: str = Field(pattern=r"^[A-Za-z0-9._:-]{1,80}$")
    verification_ttl_minutes: int = Field(ge=1, le=10080)


class VerificationDraft(Mutation):
    patient_id: UUID
    contact_id: UUID
    relationship: Literal["self", "dependent", "authorized_other"]
    identity_checked: Literal[True]
    authority_checked: Literal[True]
    evidence_reference: str = Field(pattern=r"^[A-Za-z0-9._:-]{1,80}$")


class QueueWindow(Command):
    weekday: int = Field(ge=0, le=6)
    start_minute: int = Field(ge=0, le=1439)
    end_minute: int = Field(ge=1, le=1440)

    @model_validator(mode="after")
    def interval(self) -> Self:
        if self.end_minute <= self.start_minute:
            raise ValueError("Intervalo inválido")
        return self


class QueueDraft(Versioned):
    name: str = Field(min_length=1, max_length=120)
    kind: Literal["general", "financial", "administrative"]
    active: bool
    hours: list[QueueWindow] = Field(max_length=21)
    outside_hours_notice: str = Field(min_length=1, max_length=300)

    @model_validator(mode="after")
    def configured(self) -> Self:
        if self.active and not self.hours:
            raise ValueError("Defina o expediente antes de ativar")
        return self


class HandoffDraft(Mutation):
    contact_id: UUID
    queue_id: UUID
    reason_code: Literal[
        "patient_request", "financial", "administrative", "identity_verification", "other"
    ]


class ReplyDraft(Versioned):
    text: str = Field(min_length=1, max_length=4000)

    @field_validator("text")
    @classmethod
    def not_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Mensagem obrigatória")
        return value


class IntegrationDraft(Versioned):
    credentials: dict[str, SecretStr] = Field(
        min_length=1, max_length=7, json_schema_extra={"writeOnly": True}
    )


class ChannelProvisionDraft(Versioned):
    """No secrets or caller-supplied tenant IDs are accepted."""


class TenantDraft(Versioned):
    name: str = Field(min_length=1, max_length=120)
    timezone: str = Field(min_length=1, max_length=64)
    active: bool
    registration: ClinicDetails | None = None

    @field_validator("timezone")
    @classmethod
    def timezone_valid(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError("Fuso IANA inválido") from error
        return value


class PlatformUserStatus(Mutation):
    active: bool


class BreakGlassDecision(Versioned):
    decision: Literal["approve", "reject", "revoke"]
