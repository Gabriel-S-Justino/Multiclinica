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


class IntegrationStep(View):
    code: str
    done: bool


class IntegrationHealth(View):
    worker_online: bool
    worker_seen_at: str | None
    last_event_at: str | None
    webhook_verified_at: str | None
    failed_deliveries: int
    credentials_rejected: bool


class IntegrationView(View):
    provider: str
    configured: bool
    version: int
    updated_at: str | None
    verification_status: str
    setup_complete: bool
    metadata: dict[str, str]
    channel_id: str | None
    webhook_url: str | None
    send_enabled: bool
    pending_steps: list[str]
    steps: list[IntegrationStep]
    health: IntegrationHealth | None


class IntegrationsView(View):
    items: list[IntegrationView]


class AuditView(View):
    id: str
    action: str
    resource_id: str | None
    created_at: str
    correlation_id: str
