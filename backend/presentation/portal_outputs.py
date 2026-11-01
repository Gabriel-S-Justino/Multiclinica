from pydantic import BaseModel, ConfigDict


class View(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Page[T](View):
    items: list[T]
    next_cursor: str | None = None


class AppointmentView(View):
    id: str
    status: str
    version: int
    patient_id: str
    contact_id: str
    patient_name: str | None
    service_id: str
    service_name: str | None
    professional_id: str
    professional_name: str | None
    unit_id: str
    unit_name: str | None
    starts_at: str
    ends_at: str
    duration_minutes: int
    timezone: str
    local_date: str
    local_start: str
    local_end: str
    identity_verified: bool
    actions: list[str]


class AppointmentPage(Page[AppointmentView]):
    timezone: str


class SlotView(View):
    professional_id: str
    starts_at: str
    ends_at: str
    local_date: str
    local_start: str
    local_end: str


class AvailabilityPage(Page[SlotView]):
    timezone: str


class HoldSummary(View):
    hold_id: str
    service_name: str
    professional_name: str
    unit_name: str
    duration_minutes: int
    starts_at: str
    local_date: str
    local_start: str
    expires_at: str
    timezone: str


class HandoffView(View):
    id: str
    conversation_id: str
    queue_id: str
    queue_name: str
    reason_code: str
    status: str
    version: int
    assigned_to_me: bool
    created_at: str


class MessageView(View):
    id: str
    direction: str
    text: str
    delivery_status: str
    created_at: str


class MessagePage(Page[MessageView]):
    handoff: HandoffView


class IntegrationView(View):
    provider: str
    configured: bool
    version: int
    updated_at: str | None
    verification_status: str


class IntegrationsView(View):
    items: list[IntegrationView]


class AuditView(View):
    id: str
    action: str
    resource_id: str | None
    created_at: str
    correlation_id: str
