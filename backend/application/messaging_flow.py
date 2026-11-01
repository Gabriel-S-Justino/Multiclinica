"""Deterministic contact-bound flow. State is persisted by the queue transaction."""

import json
import secrets
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.application.scheduling import Scheduler
from backend.application.scheduling_commands import (
    AppointmentMutation,
    AvailabilityQuery,
    ConfirmRequest,
    HoldRequest,
    NewPatient,
    ReleaseRequest,
    RescheduleRequest,
)
from backend.config import Settings
from backend.domain.permissions import ContactPrincipal
from backend.domain.scheduling import SchedulingError
from backend.infrastructure.fields import seal, unseal
from backend.infrastructure.messaging_models import Dispatch, MessagingChannel, MessagingSession
from backend.infrastructure.models import Professional, Tenant, Unit
from backend.infrastructure.portal_models import Handoff, Message, ServiceQueue
from backend.infrastructure.scheduling_models import (
    Appointment,
    AppointmentHold,
    ContactPatientLink,
    ConversationState,
    Patient,
    ProfessionalSchedule,
    ProfessionalService,
    Service,
)


class Flow:
    def __init__(
        self,
        db: Session,
        settings: Settings,
        channel: MessagingChannel,
        session: MessagingSession,
        state: ConversationState,
        now: datetime,
        event_key: str,
    ):
        self.db, self.settings, self.channel, self.session, self.state, self.now, self.key = (
            db,
            settings,
            channel,
            session,
            state,
            now,
            event_key,
        )
        self.data: dict[str, Any] = json.loads(
            unseal(
                settings,
                channel.tenant_id,
                "messaging_session",
                session.id,
                "context",
                session.context_ciphertext,
            )
        )
        self.identity = ContactPrincipal(
            user_id=channel.actor_user_id,
            tenant_id=channel.tenant_id,
            membership_id=channel.actor_membership_id,
            role="messaging",
            mfa_verified=False,
            channel_id=channel.id,
            contact_id=session.contact_id,
        )
        self.scheduler = Scheduler(db, settings, self.identity)
        self.scheduler._authorize()
        self.tenant = db.get(Tenant, channel.tenant_id)
        self.zone = ZoneInfo(self.tenant.timezone if self.tenant else "UTC")

    def save(self) -> None:
        self.session.context_ciphertext = seal(
            self.settings,
            self.channel.tenant_id,
            "messaging_session",
            self.session.id,
            "context",
            json.dumps(self.data),
        )
        self.state.context = {}  # no patient draft or selection data in plaintext JSONB
        self.state.version += 1
        self.session.last_processed_at = self.now

    def say(self, text: str) -> None:
        message_id = uuid4()
        self.db.add(
            Message(
                id=message_id,
                tenant_id=self.channel.tenant_id,
                conversation_id=self.session.conversation_id,
                body_ciphertext=seal(
                    self.settings, self.channel.tenant_id, "message", message_id, "body", text
                ),
                direction="outbound",
                delivery_status="queued",
                created_at=self.now,
            )
        )
        self.db.flush()
        self.db.add(
            Dispatch(
                tenant_id=self.channel.tenant_id,
                message_id=message_id,
                session_id=self.session.id,
                available_at=self.now,
            )
        )

    def choose(self, state: str, prompt: str, options: list[tuple[str, dict[str, Any]]]) -> None:
        nonce = secrets.token_hex(3)
        self.state.state = state
        self.data["options"] = {
            f"{nonce}:{index + 1}": value for index, (_, value) in enumerate(options)
        }
        self.say(
            prompt
            + "\n"
            + "\n".join(
                f"{nonce}:{index + 1} — {label}" for index, (label, _) in enumerate(options)
            )
            + "\nResponda com o código completo. Menu, voltar, cancelar fluxo ou humano."
        )

    def release(self) -> None:
        if self.data.get("hold_id"):
            try:
                self.scheduler.release_hold(
                    ReleaseRequest(
                        idempotency_key=f"release:{self.key}",
                        hold_id=UUID(self.data["hold_id"]),
                        contact_id=self.session.contact_id,
                    )
                )
            except SchedulingError:
                pass  # expiry still applies; never cancel an appointment here
        self.data.pop("hold_id", None)

    def menu(self) -> None:
        self.release()
        self.data = {}
        self.choose(
            "MENU",
            "Olá! Posso ajudar com agendamentos e atendimento.",
            [
                ("Agendar", {"action": "book"}),
                ("Minhas consultas", {"action": "manage"}),
                ("Atendimento humano", {"action": "human"}),
            ],
        )

    def handoff(self, queue_id: UUID | None = None) -> None:
        queue = self.db.scalar(
            select(ServiceQueue).where(
                ServiceQueue.id == (queue_id or self.channel.default_queue_id),
                ServiceQueue.tenant_id == self.channel.tenant_id,
                ServiceQueue.active.is_(True),
            )
        )
        if not queue:
            self.say(
                "O atendimento está indisponível neste momento. Procure a clínica pelo canal habitual."
            )
            return
        self.release()
        self.state.state, self.data = "HUMAN_HANDOFF", {}
        existing = self.db.scalar(
            select(Handoff).where(
                Handoff.tenant_id == self.channel.tenant_id,
                Handoff.conversation_id == self.session.conversation_id,
                Handoff.status.in_(["waiting", "assigned"]),
            )
        )
        if not existing:
            self.db.add(
                Handoff(
                    tenant_id=self.channel.tenant_id,
                    conversation_id=self.session.conversation_id,
                    queue_id=queue.id,
                    reason_code="patient_request",
                    created_at=self.now,
                )
            )
        local = self.now.astimezone(self.zone)
        opened = any(
            item["weekday"] == local.weekday()
            and item["start_minute"] <= local.hour * 60 + local.minute < item["end_minute"]
            for item in queue.hours
        )
        self.say(
            "Solicitação registrada para atendimento humano."
            + ("" if opened else " " + queue.outside_hours_notice)
        )

    def services(self, offset: int = 0) -> None:
        rows = list(
            self.db.scalars(
                select(Service)
                .where(Service.tenant_id == self.channel.tenant_id, Service.active.is_(True))
                .order_by(Service.display_order, Service.id)
                .offset(offset)
                .limit(9)
            )
        )
        options: list[tuple[str, dict[str, Any]]] = [
            (row.name, {"service_id": str(row.id)})
            for row in rows[:8]
            if not row.requires_professional or row.policy_validated
        ]
        if len(rows) > 8:
            options.append(("Mais serviços", {"offset": offset + 8}))
        if not options:
            self.say(
                "Nenhum serviço disponível para agendamento. Digite humano para solicitar atendimento."
            )
            return
        self.choose("SERVICE", "Qual atendimento você procura?", options)

    def units(self, offset: int = 0) -> None:
        rows = list(
            self.db.scalars(
                select(Unit)
                .where(Unit.tenant_id == self.channel.tenant_id, Unit.active.is_(True))
                .order_by(Unit.id)
                .offset(offset)
                .limit(9)
            )
        )
        options: list[tuple[str, dict[str, Any]]] = [
            (row.name, {"unit_id": str(row.id)}) for row in rows[:8]
        ]
        if len(rows) > 8:
            options.append(("Mais unidades", {"offset": offset + 8}))
        self.choose("UNIT", "Escolha a unidade:", options)

    def professionals(self, offset: int = 0) -> None:
        rows = list(
            self.db.scalars(
                select(Professional)
                .join(
                    ProfessionalService,
                    (ProfessionalService.professional_id == Professional.id)
                    & (ProfessionalService.tenant_id == Professional.tenant_id),
                )
                .where(
                    Professional.tenant_id == self.channel.tenant_id,
                    Professional.active.is_(True),
                    ProfessionalService.service_id == UUID(self.data["service_id"]),
                    ProfessionalService.active.is_(True),
                    Professional.id.in_(
                        select(ProfessionalSchedule.professional_id).where(
                            ProfessionalSchedule.tenant_id == self.channel.tenant_id,
                            ProfessionalSchedule.unit_id == UUID(self.data["unit_id"]),
                        )
                    ),
                )
                .order_by(Professional.id)
                .offset(offset)
                .limit(8)
            )
        )
        options: list[tuple[str, dict[str, Any]]] = [("Sem preferência", {"professional_id": None})]
        options += [(row.display_name, {"professional_id": str(row.id)}) for row in rows[:7]]
        if len(rows) > 7:
            options.append(("Mais profissionais", {"offset": offset + 7}))
        self.choose("PROFESSIONAL", "Você tem preferência por profissional?", options)

    def query(self, day: date, offset: int = 0) -> Any:
        return self.scheduler.availability(
            AvailabilityQuery(
                service_id=UUID(self.data["service_id"]),
                unit_id=UUID(self.data["unit_id"]),
                professional_id=UUID(self.data["professional_id"])
                if self.data.get("professional_id")
                else None,
                first_date=day,
                last_date=day,
                offset=offset,
                limit=8,
            )
        )

    def days(self, offset: int = 0) -> None:
        service = self.db.get(Service, UUID(self.data["service_id"]))
        if not service:
            raise SchedulingError("service_unavailable")
        today = self.now.astimezone(self.zone).date()
        options: list[tuple[str, dict[str, Any]]] = []
        for index in range(offset, min(offset + 7, service.horizon_days + 1)):
            day = today + timedelta(days=index)
            if self.query(day).items:
                options.append((day.strftime("%d/%m/%Y"), {"date": day.isoformat()}))
        if offset + 7 <= service.horizon_days:
            options.append(("Próxima semana", {"offset": offset + 7}))
        self.choose(
            "DATE",
            "Escolha uma data disponível:"
            if options
            else "Nenhuma data disponível nesta semana. Digite voltar ou humano.",
            options,
        )

    def times(self, offset: int = 0) -> None:
        result = self.query(date.fromisoformat(self.data["date"]), offset)
        options: list[tuple[str, dict[str, Any]]] = [
            (
                f"{row.start.astimezone(self.zone):%H:%M}",
                {"starts_at": row.start.isoformat(), "professional_id": str(row.professional_id)},
            )
            for row in result.items
        ]
        if result.next_offset is not None:
            options.append(("Mais horários", {"offset": result.next_offset}))
        self.choose("TIME", "Escolha um horário:", options)

    def verified_appointments(self) -> list[Appointment]:
        links = select(ContactPatientLink.patient_id).where(
            ContactPatientLink.tenant_id == self.channel.tenant_id,
            ContactPatientLink.contact_id == self.session.contact_id,
            ContactPatientLink.revoked.is_(False),
            ContactPatientLink.verification_method == "manual_clinic",
            ContactPatientLink.verified_by.is_not(None),
            ContactPatientLink.verified_at <= self.now,
            ContactPatientLink.verified_until > self.now,
        )
        return list(
            self.db.scalars(
                select(Appointment)
                .where(
                    Appointment.tenant_id == self.channel.tenant_id,
                    Appointment.contact_id == self.session.contact_id,
                    Appointment.patient_id.in_(links),
                    Appointment.status.in_(["scheduled", "confirmed"]),
                )
                .order_by(Appointment.starts_at)
                .limit(50)
            )
        )

    def manage(self, offset: int = 0) -> None:
        rows = self.verified_appointments()
        if not rows:
            self.say(
                "Para consultar ou alterar agendamentos, precisamos verificar seu vínculo com a equipe. Digite humano para continuar."
            )
            return
        options: list[tuple[str, dict[str, Any]]] = [
            (
                f"{row.starts_at.astimezone(self.zone):%d/%m %H:%M} · {self.patient_name(row.patient_id)}",
                {"appointment_id": str(row.id), "version": row.version},
            )
            for row in rows[offset : offset + 8]
        ]
        if offset + 8 < len(rows):
            options.append(("Mais consultas", {"offset": offset + 8}))
        self.choose(
            "APPOINTMENT",
            "Escolha a consulta:",
            options,
        )

    def patient_name(self, patient_id: UUID) -> str:
        patient = self.db.get(Patient, patient_id)
        if not patient or patient.tenant_id != self.channel.tenant_id:
            raise SchedulingError("identity_unverified")
        return unseal(
            self.settings,
            self.channel.tenant_id,
            "patient",
            patient.id,
            "name",
            patient.name_ciphertext,
        )

    def review(self) -> None:
        hold = self.db.get(AppointmentHold, UUID(self.data["hold_id"]))
        if not hold or hold.expires_at <= self.now:
            raise SchedulingError("hold_unavailable")
        service, unit, professional = (
            self.db.get(Service, hold.service_id),
            self.db.get(Unit, hold.unit_id),
            self.db.get(Professional, hold.professional_id),
        )
        if not service or not unit or not professional:
            raise SchedulingError("hold_unavailable")
        patient = self.data.get("patient_name", "")
        self.choose(
            "REVIEW",
            f"Revise antes de confirmar:\n{service.name}\n{professional.display_name}\n{hold.starts_at.astimezone(self.zone):%d/%m/%Y %H:%M} ({self.zone.key})\n{unit.name}\n{hold.duration_minutes} minutos\nPaciente: {patient}\nReserva temporária; ainda não é consulta confirmada.",
            [("Confirmar", {"confirm": True}), ("Cancelar fluxo", {"confirm": False})],
        )

    def handle(self, text: str, kind: str) -> None:
        value = text.strip()
        command = value.casefold()
        if command == "parar":
            self.release()
            self.session.opted_out = True
            self.data = {}
            if self.state.state != "HUMAN_HANDOFF":
                self.state.state = "DONE"
                self.say("Preferência registrada. Para iniciar novo atendimento, envie retomar.")
            return
        if self.state.state == "HUMAN_HANDOFF":
            return
        if self.session.opted_out:
            if command != "retomar":
                return
            self.session.opted_out = False
            self.menu()
            return
        if (
            self.session.last_processed_at
            and self.now - self.session.last_processed_at
            > timedelta(minutes=self.channel.idle_minutes)
            and self.state.state not in {"MENU", "DONE", "RESUME"}
        ):
            self.data["resume_state"] = self.state.state
            self.choose(
                "RESUME",
                "Seu atendimento ficou inativo. Deseja continuar? O horário será verificado novamente.",
                [("Retomar", {"resume": True}), ("Reiniciar", {"resume": False})],
            )
            return
        if command in {"menu", "reiniciar", "cancelar fluxo"}:
            self.menu()
            return
        if command == "humano":
            self.handoff()
            return
        if command == "voltar":
            self.release()
            if "service_id" in self.data:
                self.days() if "unit_id" in self.data else self.units()
            else:
                self.menu()
            return
        if kind != "text":
            self.say(
                "No momento, atendemos apenas por texto. Envie menu ou humano. Não é necessário reenviar a mídia."
            )
            return
        stage = self.state.state
        if stage in {"DONE", "START"}:
            self.menu()
            return
        if stage == "NAME":
            self.data["patient_name"] = NewPatient(
                display_name=value, purpose_acknowledged=True
            ).display_name
            service = self.db.get(Service, UUID(self.data["service_id"]))
            if service and service.requires_birth_date:
                self.state.state = "BIRTH_DATE"
                self.say(
                    "Informe a data de nascimento no formato AAAA-MM-DD, exigida pela clínica para este serviço."
                )
            else:
                self.review()
            return
        if stage == "BIRTH_DATE":
            self.data["birth_date"] = date.fromisoformat(value).isoformat()
            self.review()
            return
        option = self.data.get("options", {}).get(value)
        if option is None:
            self.data["ambiguity"] = self.data.get("ambiguity", 0) + 1
            if self.data["ambiguity"] >= self.channel.ambiguity_limit:
                self.say(
                    "Não consegui identificar a opção. Envie menu para recomeçar ou humano para atendimento."
                )
            else:
                self.say(
                    "Responda com o código completo da opção. Se preferir, envie menu ou humano."
                )
            return
        self.data["ambiguity"] = 0
        if stage == "RESUME":
            if option["resume"] and self.data.get("hold_id"):
                self.review()
            else:
                self.menu()
        elif stage == "MENU":
            if option["action"] == "book":
                self.services()
            elif option["action"] == "manage":
                self.manage()
            else:
                self.handoff()
        elif stage == "SERVICE":
            if "offset" in option:
                self.services(option["offset"])
            else:
                service = self.db.get(Service, UUID(option["service_id"]))
                if not service or not service.active:
                    raise SchedulingError("service_unavailable")
                self.data.update(option)
                self.units() if service.requires_professional else self.handoff(
                    service.service_queue_id
                )
        elif stage == "UNIT":
            if "offset" in option:
                self.units(option["offset"])
            else:
                self.data.update(option)
                self.professionals()
        elif stage == "PROFESSIONAL":
            if "offset" in option:
                self.professionals(option["offset"])
            else:
                self.data.update(option)
                self.days()
        elif stage == "DATE":
            if "offset" in option:
                self.days(option["offset"])
            else:
                self.data.update(option)
                self.times()
        elif stage == "TIME":
            if "offset" in option:
                self.times(option["offset"])
            else:
                args = (
                    {
                        "reschedule_appointment_id": UUID(self.data["appointment_id"]),
                        "appointment_version": self.data["appointment_version"],
                    }
                    if self.data.get("appointment_id")
                    else {}
                )
                hold = self.scheduler.create_hold(
                    HoldRequest(
                        idempotency_key=f"hold:{self.key}",
                        service_id=UUID(self.data["service_id"]),
                        unit_id=UUID(self.data["unit_id"]),
                        contact_id=self.session.contact_id,
                        professional_id=UUID(option["professional_id"]),
                        starts_at=datetime.fromisoformat(option["starts_at"]),
                        **args,
                    )
                )
                self.data["hold_id"] = hold["hold_id"]
                if self.data.get("appointment_id"):
                    self.review()
                else:
                    self.choose(
                        "PURPOSE",
                        "Estes dados serão usados apenas para cadastrar e agendar o paciente. Para paciente já cadastrado, solicite verificação humana; não crie outro cadastro.",
                        [
                            ("Cadastrar novo paciente", {"purpose": True}),
                            ("Paciente já cadastrado", {"purpose": False}),
                        ],
                    )
        elif stage == "PURPOSE":
            if option["purpose"]:
                self.state.state = "NAME"
                self.say(
                    "Informe o nome do paciente, que pode ser você ou um dependente autorizado. Não envie documentos ou informações clínicas."
                )
            else:
                self.handoff()
        elif stage == "REVIEW":
            if not option["confirm"]:
                self.menu()
            else:
                if self.data.get("appointment_id"):
                    self.scheduler.reschedule(
                        RescheduleRequest(
                            idempotency_key=f"reschedule:{self.key}",
                            appointment_id=UUID(self.data["appointment_id"]),
                            contact_id=self.session.contact_id,
                            version=self.data["appointment_version"],
                            hold_id=UUID(self.data["hold_id"]),
                        )
                    )
                    message = "Consulta remarcada com sucesso."
                else:
                    self.scheduler.confirm(
                        ConfirmRequest(
                            idempotency_key=f"confirm:{self.key}",
                            hold_id=UUID(self.data["hold_id"]),
                            contact_id=self.session.contact_id,
                            new_patient=NewPatient(
                                display_name=self.data["patient_name"],
                                birth_date=date.fromisoformat(self.data["birth_date"])
                                if self.data.get("birth_date")
                                else None,
                                purpose_acknowledged=True,
                            ),
                        )
                    )
                    message = "Agendamento confirmado com sucesso."
                self.data, self.state.state = {}, "DONE"
                self.say(message + " Envie menu para novo atendimento.")
        elif stage == "APPOINTMENT":
            if "offset" in option:
                self.manage(option["offset"])
                return
            row = next(
                (
                    item
                    for item in self.verified_appointments()
                    if str(item.id) == option["appointment_id"]
                    and item.version == option["version"]
                ),
                None,
            )
            if not row:
                raise SchedulingError("appointment_unavailable")
            self.data.update(
                appointment_id=str(row.id),
                appointment_version=row.version,
                service_id=str(row.service_id),
                unit_id=str(row.unit_id),
                professional_id=None,
                patient_name=self.patient_name(row.patient_id),
            )
            self.choose(
                "MANAGE",
                "O que deseja fazer?",
                [
                    ("Cancelar consulta", {"action": "cancel"}),
                    ("Remarcar", {"action": "reschedule"}),
                ],
            )
        elif stage == "MANAGE":
            if option["action"] == "cancel":
                self.choose(
                    "CANCEL",
                    "Confirma o cancelamento da consulta selecionada?",
                    [
                        ("Confirmar cancelamento", {"confirm": True}),
                        ("Manter consulta", {"confirm": False}),
                    ],
                )
            else:
                self.days()
        elif stage == "CANCEL":
            if option["confirm"]:
                self.scheduler.cancel(
                    AppointmentMutation(
                        idempotency_key=f"cancel:{self.key}",
                        appointment_id=UUID(self.data["appointment_id"]),
                        contact_id=self.session.contact_id,
                        version=self.data["appointment_version"],
                    )
                )
                self.data, self.state.state = {}, "DONE"
                self.say("Consulta cancelada com sucesso. Envie menu para novo atendimento.")
            else:
                self.menu()
