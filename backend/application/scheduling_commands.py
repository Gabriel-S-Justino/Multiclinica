from datetime import date, datetime
from typing import Self
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from backend.application.contracts import Command
from backend.domain.scheduling import utc


class AvailabilityQuery(Command):
    service_id: UUID
    unit_id: UUID
    professional_id: UUID | None = None
    first_date: date
    last_date: date
    resource_ids: list[UUID] = Field(default_factory=list, max_length=10)
    offset: int = Field(default=0, ge=0, le=100000)
    limit: int = Field(default=25, ge=1, le=100)

    @model_validator(mode="after")
    def bounded(self) -> Self:
        if not 0 <= (self.last_date - self.first_date).days < 31:
            raise ValueError("Consulte até 31 dias de cada vez")
        if len(self.resource_ids) != len(set(self.resource_ids)):
            raise ValueError("Recurso duplicado")
        return self


class Mutation(Command):
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9._:-]{8,128}$")


class ContactRequest(Mutation):
    phone: str = Field(pattern=r"^\+[1-9][0-9]{7,14}$")


class HoldRequest(Mutation):
    service_id: UUID
    unit_id: UUID
    contact_id: UUID
    professional_id: UUID | None = None
    starts_at: datetime
    resource_ids: list[UUID] = Field(default_factory=list, max_length=10)
    conversation_id: UUID | None = None
    conversation_version: int | None = Field(default=None, ge=0)
    reschedule_appointment_id: UUID | None = None
    appointment_version: int | None = Field(default=None, ge=0)

    @field_validator("starts_at")
    @classmethod
    def aware_start(cls, value: datetime) -> datetime:
        return utc(value)

    @model_validator(mode="after")
    def paired_conversation(self) -> Self:
        if (self.reschedule_appointment_id is None) != (self.appointment_version is None):
            raise ValueError("Agendamento e versão devem ser informados juntos")
        if (self.conversation_id is None) != (self.conversation_version is None):
            raise ValueError("Conversa e versão devem ser informadas juntas")
        if len(self.resource_ids) != len(set(self.resource_ids)):
            raise ValueError("Recurso duplicado")
        return self


class NewPatient(Command):
    display_name: str = Field(min_length=1, max_length=120)
    birth_date: date | None = None
    purpose_acknowledged: bool

    @field_validator("display_name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Nome obrigatório")
        return cleaned


class ConfirmRequest(Mutation):
    hold_id: UUID
    contact_id: UUID
    patient_id: UUID | None = None
    new_patient: NewPatient | None = None
    conversation_version: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def patient_choice(self) -> Self:
        if (self.patient_id is None) == (self.new_patient is None):
            raise ValueError("Informe paciente existente ou novo")
        return self


class AppointmentMutation(Mutation):
    appointment_id: UUID
    contact_id: UUID
    version: int = Field(ge=0)


class RescheduleRequest(AppointmentMutation):
    hold_id: UUID
    conversation_version: int | None = Field(default=None, ge=0)


class TransitionRequest(AppointmentMutation):
    target_status: str = Field(pattern=r"^(confirmed|completed|no_show)$")


class ReleaseRequest(Mutation):
    hold_id: UUID
    contact_id: UUID
