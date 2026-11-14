from datetime import date
from typing import Any, Literal
from uuid import UUID

from fastapi import Depends, FastAPI, Query, Request, Response
from fastapi.routing import APIRoute
from sqlalchemy.orm import Session

from backend.application import auth, invitations
from backend.application.clinic_admin import ClinicAdmin
from backend.application.inbox import Inbox
from backend.application.integrations import Integrations
from backend.application.platform_admin import PlatformAdmin
from backend.application.portal_access import PortalContext, PortalError
from backend.application.portal_commands import (
    BlockDraft,
    BreakGlassDecision,
    ChannelProvisionDraft,
    ClinicPolicyDraft,
    ExceptionDraft,
    HandoffDraft,
    IntegrationDraft,
    InvitationDraft,
    MembershipDraft,
    PlatformInvitationDraft,
    PlatformUserPhoto,
    PlatformUserProfile,
    PlatformUserStatus,
    ProfessionalDraft,
    QueueDraft,
    ReplyDraft,
    ResourceDraft,
    ScheduleDraft,
    ServiceDraft,
    TenantDraft,
    UnitDraft,
    VerificationDraft,
    Versioned,
)
from backend.application.portal_read import PortalRead
from backend.application.scheduling import Scheduler
from backend.application.scheduling_commands import (
    AppointmentMutation,
    AvailabilityQuery,
    ConfirmRequest,
    ContactRequest,
    HoldRequest,
    Mutation,
    ReleaseRequest,
    RescheduleRequest,
    TransitionRequest,
)
from backend.config import Settings
from backend.domain.permissions import Principal
from backend.infrastructure.models import PortalSession
from backend.infrastructure.portal_models import PlatformOperator
from backend.presentation.portal_outputs import (
    AppointmentPage,
    AppointmentView,
    AuditView,
    AvailabilityPage,
    HandoffView,
    HoldSummary,
    IntegrationsView,
    MessagePage,
    Page,
)
from backend.presentation.schemas import InvitationAcceptance


def register_portal_routes(
    app: FastAPI, settings: Settings, db_dependency: Any, session_dependency: Any
) -> None:
    def context(
        request: Request,
        session: PortalSession = Depends(session_dependency),
        db: Session = Depends(db_dependency, scope="function"),
    ) -> PortalContext:
        if session.membership_id is None and db.get(PlatformOperator, session.user_id) is not None:
            raise PortalError("permission_denied", 403)
        identity = auth.principal(db, session)
        request.state.tenant_id = str(identity.tenant_id)
        return PortalContext(db, settings, identity, UUID(request.state.correlation_id))

    def platform_context(
        request: Request,
        session: PortalSession = Depends(session_dependency),
        db: Session = Depends(db_dependency, scope="function"),
    ) -> PortalContext:
        identity = Principal(
            session.user_id,
            UUID(int=0),
            UUID(int=0),
            "superadmin",
            session.mfa_verified,
            session.authenticated_at,
        )
        return PortalContext(db, settings, identity, UUID(request.state.correlation_id))

    def keyed(request: Request, command: Mutation) -> None:
        if request.headers.get("Idempotency-Key") != command.idempotency_key:
            raise PortalError("idempotency_key_required", 422)

    @app.get("/v1/portal/catalog")
    def catalog(ctx: PortalContext = Depends(context)) -> dict[str, Any]:
        return ClinicAdmin(ctx).catalog()

    @app.get("/v1/services")
    def services(ctx: PortalContext = Depends(context)) -> dict[str, Any]:
        return ClinicAdmin(ctx).services()

    @app.post("/v1/services")
    def create_service(
        command: ServiceDraft, request: Request, ctx: PortalContext = Depends(context)
    ) -> dict[str, Any]:
        keyed(request, command)
        return ClinicAdmin(ctx).save_service(command)

    @app.patch("/v1/services/{entity_id}")
    def update_service(
        entity_id: UUID,
        command: ServiceDraft,
        request: Request,
        ctx: PortalContext = Depends(context),
    ) -> dict[str, Any]:
        keyed(request, command)
        return ClinicAdmin(ctx).save_service(command, entity_id)

    @app.delete("/v1/services/{entity_id}")
    def delete_service(
        entity_id: UUID, command: Versioned, request: Request, ctx: PortalContext = Depends(context)
    ) -> dict[str, Any]:
        keyed(request, command)
        return ClinicAdmin(ctx).deactivate_service(command, entity_id)

    @app.get("/v1/team/professionals")
    def team_professionals(ctx: PortalContext = Depends(context)) -> dict[str, Any]:
        return ClinicAdmin(ctx).professionals()

    @app.post("/v1/team/professionals")
    def create_professional(
        command: ProfessionalDraft, request: Request, ctx: PortalContext = Depends(context)
    ) -> dict[str, Any]:
        keyed(request, command)
        return ClinicAdmin(ctx).save_professional(command)

    @app.patch("/v1/team/professionals/{entity_id}")
    def update_professional(
        entity_id: UUID,
        command: ProfessionalDraft,
        request: Request,
        ctx: PortalContext = Depends(context),
    ) -> dict[str, Any]:
        keyed(request, command)
        return ClinicAdmin(ctx).save_professional(command, entity_id)

    @app.get("/v1/team/memberships")
    def memberships(
        limit: int = Query(100, ge=1, le=100),
        cursor: str | None = Query(None, max_length=2048),
        ctx: PortalContext = Depends(context),
    ) -> dict[str, Any]:
        return ClinicAdmin(ctx).team(limit, cursor)

    @app.patch("/v1/team/memberships/{entity_id}")
    def update_membership(
        entity_id: UUID,
        command: MembershipDraft,
        request: Request,
        ctx: PortalContext = Depends(context),
    ) -> dict[str, Any]:
        keyed(request, command)
        return ClinicAdmin(ctx).save_membership(command, entity_id)

    @app.post("/v1/team/invitations", status_code=202)
    def invite(
        command: InvitationDraft, request: Request, ctx: PortalContext = Depends(context)
    ) -> dict[str, Any]:
        keyed(request, command)
        return invitations.activation_receipt(settings, ClinicAdmin(ctx).invite(command))

    @app.delete("/v1/team/memberships/{entity_id}")
    def remove_membership(
        entity_id: UUID, command: Versioned, request: Request, ctx: PortalContext = Depends(context)
    ) -> dict[str, Any]:
        keyed(request, command)
        return ClinicAdmin(ctx).remove_membership(command, entity_id)

    @app.get("/v1/auth/invitations")
    def invitations_for_user(
        session: PortalSession = Depends(session_dependency),
        db: Session = Depends(db_dependency, scope="function"),
    ) -> dict[str, Any]:
        return invitations.list_invitations(db, settings, session)

    @app.post("/v1/auth/invitations/{invitation_id}/accept")
    def accept_invitation(
        invitation_id: UUID,
        command: InvitationAcceptance,
        request: Request,
        session: PortalSession = Depends(session_dependency),
        db: Session = Depends(db_dependency, scope="function"),
    ) -> dict[str, Any]:
        return invitations.accept_invitation(
            db,
            settings,
            session,
            invitation_id,
            UUID(request.state.correlation_id),
            command.activation_code,
        )

    @app.get("/v1/schedules")
    def schedules(professional_id: UUID, ctx: PortalContext = Depends(context)) -> dict[str, Any]:
        return ClinicAdmin(ctx).schedules(professional_id)

    @app.post("/v1/schedules")
    def create_schedule(
        command: ScheduleDraft, request: Request, ctx: PortalContext = Depends(context)
    ) -> dict[str, Any]:
        keyed(request, command)
        return ClinicAdmin(ctx).save_schedule(command, "schedule")

    @app.patch("/v1/schedules/{entity_id}")
    def update_schedule(
        entity_id: UUID,
        command: ScheduleDraft,
        request: Request,
        ctx: PortalContext = Depends(context),
    ) -> dict[str, Any]:
        keyed(request, command)
        return ClinicAdmin(ctx).save_schedule(command, "schedule", entity_id)

    @app.delete("/v1/schedules/{entity_id}")
    def delete_schedule(
        entity_id: UUID, command: Versioned, request: Request, ctx: PortalContext = Depends(context)
    ) -> dict[str, Any]:
        keyed(request, command)
        return ClinicAdmin(ctx).delete_schedule(command, "schedule", entity_id)

    @app.post("/v1/schedule-exceptions")
    def create_exception(
        command: ExceptionDraft, request: Request, ctx: PortalContext = Depends(context)
    ) -> dict[str, Any]:
        keyed(request, command)
        return ClinicAdmin(ctx).save_schedule(command, "exception")

    @app.patch("/v1/schedule-exceptions/{entity_id}")
    def update_exception(
        entity_id: UUID,
        command: ExceptionDraft,
        request: Request,
        ctx: PortalContext = Depends(context),
    ) -> dict[str, Any]:
        keyed(request, command)
        return ClinicAdmin(ctx).save_schedule(command, "exception", entity_id)

    @app.delete("/v1/schedule-exceptions/{entity_id}")
    def delete_exception(
        entity_id: UUID, command: Versioned, request: Request, ctx: PortalContext = Depends(context)
    ) -> dict[str, Any]:
        keyed(request, command)
        return ClinicAdmin(ctx).delete_schedule(command, "exception", entity_id)

    @app.post("/v1/blocked-periods")
    def create_block(
        command: BlockDraft, request: Request, ctx: PortalContext = Depends(context)
    ) -> dict[str, Any]:
        keyed(request, command)
        return ClinicAdmin(ctx).save_schedule(command, "block")

    @app.delete("/v1/blocked-periods/{entity_id}")
    def delete_block(
        entity_id: UUID, command: Versioned, request: Request, ctx: PortalContext = Depends(context)
    ) -> dict[str, Any]:
        keyed(request, command)
        return ClinicAdmin(ctx).delete_schedule(command, "block", entity_id)

    @app.get("/v1/units")
    def units(ctx: PortalContext = Depends(context)) -> dict[str, Any]:
        return ClinicAdmin(ctx).units()

    @app.post("/v1/units")
    def create_unit(
        command: UnitDraft, request: Request, ctx: PortalContext = Depends(context)
    ) -> dict[str, Any]:
        keyed(request, command)
        return ClinicAdmin(ctx).save_unit(command)

    @app.patch("/v1/units/{entity_id}")
    def update_unit(
        entity_id: UUID, command: UnitDraft, request: Request, ctx: PortalContext = Depends(context)
    ) -> dict[str, Any]:
        keyed(request, command)
        return ClinicAdmin(ctx).save_unit(command, entity_id)

    @app.post("/v1/resources")
    def create_resource(
        command: ResourceDraft, request: Request, ctx: PortalContext = Depends(context)
    ) -> dict[str, Any]:
        keyed(request, command)
        return ClinicAdmin(ctx).save_unit(command)

    @app.patch("/v1/resources/{entity_id}")
    def update_resource(
        entity_id: UUID,
        command: ResourceDraft,
        request: Request,
        ctx: PortalContext = Depends(context),
    ) -> dict[str, Any]:
        keyed(request, command)
        return ClinicAdmin(ctx).save_unit(command, entity_id)

    @app.get("/v1/clinic-policy")
    def policy(ctx: PortalContext = Depends(context)) -> dict[str, Any]:
        return ClinicAdmin(ctx).policy()

    @app.put("/v1/clinic-policy")
    def save_policy(
        command: ClinicPolicyDraft, request: Request, ctx: PortalContext = Depends(context)
    ) -> dict[str, Any]:
        keyed(request, command)
        return ClinicAdmin(ctx).save_policy(command)

    @app.post("/v1/patient-verifications")
    def verify_patient(
        command: VerificationDraft, request: Request, ctx: PortalContext = Depends(context)
    ) -> dict[str, Any]:
        keyed(request, command)
        return ClinicAdmin(ctx).verify_patient(command)

    @app.get("/v1/appointments", response_model=AppointmentPage)
    def appointments(
        first_date: date,
        last_date: date,
        professional_id: UUID | None = None,
        limit: int = Query(25, ge=1, le=100),
        cursor: str | None = Query(None, max_length=2048),
        ctx: PortalContext = Depends(context),
    ) -> dict[str, Any]:
        return PortalRead(ctx).appointments(first_date, last_date, professional_id, limit, cursor)

    @app.get("/v1/appointments/{appointment_id}", response_model=AppointmentView)
    def appointment(appointment_id: UUID, ctx: PortalContext = Depends(context)) -> dict[str, Any]:
        reader = PortalRead(ctx)
        return reader.describe(reader.appointment(appointment_id))

    @app.get("/v1/availability", response_model=AvailabilityPage)
    def availability(
        service_id: UUID,
        unit_id: UUID,
        first_date: date,
        last_date: date,
        professional_id: UUID | None = None,
        resource_ids: list[UUID] = Query(default=[]),
        limit: int = Query(25, ge=1, le=100),
        cursor: str | None = Query(None, max_length=2048),
        ctx: PortalContext = Depends(context),
    ) -> dict[str, Any]:
        command = AvailabilityQuery(
            service_id=service_id,
            unit_id=unit_id,
            first_date=first_date,
            last_date=last_date,
            professional_id=professional_id,
            resource_ids=resource_ids,
            limit=limit,
        )
        return PortalRead(ctx).availability(command, cursor)

    @app.post("/v1/contacts")
    def create_contact(
        command: ContactRequest, request: Request, ctx: PortalContext = Depends(context)
    ) -> dict[str, Any]:
        keyed(request, command)
        return Scheduler(ctx.db, settings, ctx.identity).register_contact(command)

    @app.get("/v1/contacts/{contact_id}/patients")
    def patients(contact_id: UUID, ctx: PortalContext = Depends(context)) -> dict[str, Any]:
        return PortalRead(ctx).patients(contact_id)

    @app.post("/v1/holds")
    def create_hold(
        command: HoldRequest, request: Request, ctx: PortalContext = Depends(context)
    ) -> dict[str, Any]:
        keyed(request, command)
        return Scheduler(ctx.db, settings, ctx.identity).create_hold(command)

    @app.get("/v1/holds/{hold_id}/summary", response_model=HoldSummary)
    def summary(hold_id: UUID, ctx: PortalContext = Depends(context)) -> dict[str, Any]:
        return PortalRead(ctx).hold_summary(hold_id)

    @app.post("/v1/holds/{hold_id}/release")
    def release_hold(
        hold_id: UUID,
        command: ReleaseRequest,
        request: Request,
        ctx: PortalContext = Depends(context),
    ) -> dict[str, Any]:
        keyed(request, command)
        if hold_id != command.hold_id:
            raise PortalError("validation_failed", 422)
        return Scheduler(ctx.db, settings, ctx.identity).release_hold(command)

    @app.post("/v1/appointments")
    def confirm(
        command: ConfirmRequest, request: Request, ctx: PortalContext = Depends(context)
    ) -> dict[str, Any]:
        keyed(request, command)
        return Scheduler(ctx.db, settings, ctx.identity).confirm(command)

    @app.post("/v1/appointments/{appointment_id}/cancel")
    def cancel(
        appointment_id: UUID,
        command: AppointmentMutation,
        request: Request,
        ctx: PortalContext = Depends(context),
    ) -> dict[str, Any]:
        keyed(request, command)
        if appointment_id != command.appointment_id:
            raise PortalError("validation_failed", 422)
        return Scheduler(ctx.db, settings, ctx.identity).cancel(command)

    @app.post("/v1/appointments/{appointment_id}/reschedule")
    def reschedule(
        appointment_id: UUID,
        command: RescheduleRequest,
        request: Request,
        ctx: PortalContext = Depends(context),
    ) -> dict[str, Any]:
        keyed(request, command)
        if appointment_id != command.appointment_id:
            raise PortalError("validation_failed", 422)
        return Scheduler(ctx.db, settings, ctx.identity).reschedule(command)

    @app.post("/v1/appointments/{appointment_id}/transitions")
    def transition(
        appointment_id: UUID,
        command: TransitionRequest,
        request: Request,
        ctx: PortalContext = Depends(context),
    ) -> dict[str, Any]:
        keyed(request, command)
        if appointment_id != command.appointment_id:
            raise PortalError("validation_failed", 422)
        return Scheduler(ctx.db, settings, ctx.identity).transition(command)

    @app.get("/v1/admin/queues")
    def admin_queues(ctx: PortalContext = Depends(context)) -> dict[str, Any]:
        return Inbox(ctx).queues(manage=True)

    @app.get("/v1/queues")
    def queues(ctx: PortalContext = Depends(context)) -> dict[str, Any]:
        return Inbox(ctx).queues()

    @app.post("/v1/admin/queues")
    def create_queue(
        command: QueueDraft, request: Request, ctx: PortalContext = Depends(context)
    ) -> dict[str, Any]:
        keyed(request, command)
        return Inbox(ctx).save_queue(command)

    @app.patch("/v1/admin/queues/{entity_id}")
    def update_queue(
        entity_id: UUID,
        command: QueueDraft,
        request: Request,
        ctx: PortalContext = Depends(context),
    ) -> dict[str, Any]:
        keyed(request, command)
        return Inbox(ctx).save_queue(command, entity_id)

    @app.get("/v1/inbox", response_model=Page[HandoffView])
    def inbox(
        limit: int = Query(25, ge=1, le=100),
        cursor: str | None = Query(None, max_length=2048),
        ctx: PortalContext = Depends(context),
    ) -> dict[str, Any]:
        return Inbox(ctx).list(limit, cursor)

    @app.post("/v1/handoffs")
    def create_handoff(
        command: HandoffDraft, request: Request, ctx: PortalContext = Depends(context)
    ) -> dict[str, Any]:
        keyed(request, command)
        return Inbox(ctx).create(command)

    @app.post("/v1/handoffs/{handoff_id}/claim")
    def handoff_claim(
        handoff_id: UUID,
        command: Versioned,
        request: Request,
        ctx: PortalContext = Depends(context),
    ) -> dict[str, Any]:
        keyed(request, command)
        return Inbox(ctx).act(command, handoff_id, "claim")

    @app.post("/v1/handoffs/{handoff_id}/release")
    def handoff_release(
        handoff_id: UUID,
        command: Versioned,
        request: Request,
        ctx: PortalContext = Depends(context),
    ) -> dict[str, Any]:
        keyed(request, command)
        return Inbox(ctx).act(command, handoff_id, "release")

    @app.post("/v1/handoffs/{handoff_id}/close")
    def handoff_close(
        handoff_id: UUID,
        command: Versioned,
        request: Request,
        ctx: PortalContext = Depends(context),
    ) -> dict[str, Any]:
        keyed(request, command)
        return Inbox(ctx).act(command, handoff_id, "close")

    @app.get("/v1/handoffs/{handoff_id}/messages", response_model=MessagePage)
    def messages(
        handoff_id: UUID,
        limit: int = Query(25, ge=1, le=100),
        cursor: str | None = Query(None, max_length=2048),
        ctx: PortalContext = Depends(context),
    ) -> dict[str, Any]:
        return Inbox(ctx).messages(handoff_id, limit, cursor)

    @app.post("/v1/handoffs/{handoff_id}/replies")
    def reply(
        handoff_id: UUID,
        command: ReplyDraft,
        request: Request,
        ctx: PortalContext = Depends(context),
    ) -> dict[str, Any]:
        keyed(request, command)
        return Inbox(ctx).reply(command, handoff_id)

    @app.get("/v1/integrations", response_model=IntegrationsView)
    def integration_states(ctx: PortalContext = Depends(context)) -> dict[str, Any]:
        return Integrations(ctx).list()

    @app.put("/v1/integrations/{provider}")
    def save_integration(
        provider: Literal["whatsapp", "ai"],
        command: IntegrationDraft,
        request: Request,
        ctx: PortalContext = Depends(context),
    ) -> dict[str, Any]:
        keyed(request, command)
        return Integrations(ctx).save(provider, command)

    @app.post("/v1/integrations/whatsapp/channel")
    def provision_whatsapp_channel(
        command: ChannelProvisionDraft,
        request: Request,
        ctx: PortalContext = Depends(context),
    ) -> dict[str, Any]:
        keyed(request, command)
        return Integrations(ctx).provision_channel(command)

    @app.post("/v1/integrations/{provider}/verify")
    def verify_integration(
        provider: Literal["whatsapp", "ai"],
        ctx: PortalContext = Depends(context),
    ) -> dict[str, str]:
        return Integrations(ctx).verify(provider)

    @app.get("/v1/audit", response_model=Page[AuditView])
    def audit(
        limit: int = Query(25, ge=1, le=100),
        cursor: str | None = Query(None, max_length=2048),
        ctx: PortalContext = Depends(context),
    ) -> dict[str, Any]:
        return PortalRead(ctx).audit(limit, cursor)

    @app.get("/v1/notifications")
    def notifications(ctx: PortalContext = Depends(context)) -> dict[str, Any]:
        return PortalRead(ctx).notifications()

    @app.get("/v1/support-requests")
    def support_requests(ctx: PortalContext = Depends(context)) -> dict[str, Any]:
        return PlatformAdmin(ctx).clinic_requests()

    @app.post("/v1/support-requests/{request_id}/decision")
    def decide_access(
        request_id: UUID,
        command: BreakGlassDecision,
        request: Request,
        ctx: PortalContext = Depends(context),
    ) -> dict[str, Any]:
        keyed(request, command)
        return PlatformAdmin(ctx).decide(command, request_id)

    @app.get("/v1/platform/tenants")
    def platform_tenants(
        limit: int = Query(25, ge=1, le=100),
        cursor: str | None = Query(None, max_length=2048),
        ctx: PortalContext = Depends(platform_context),
    ) -> dict[str, Any]:
        return PlatformAdmin(ctx).tenants(limit, cursor)

    @app.get("/v1/platform/overview")
    def platform_overview(ctx: PortalContext = Depends(platform_context)) -> dict[str, int]:
        return PlatformAdmin(ctx).overview()

    @app.get("/v1/platform/audit")
    def platform_audit(
        start: date | None = None,
        end: date | None = None,
        action: str = Query("", max_length=80),
        scope: Literal["clinic", "platform"] | None = None,
        clinic: UUID | None = None,
        limit: int = Query(50, ge=1, le=500),
        cursor: str | None = Query(None, max_length=2048),
        ctx: PortalContext = Depends(platform_context),
    ) -> dict[str, Any]:
        return PlatformAdmin(ctx).audit_events(
            limit, cursor, start, end, action.strip(), scope, clinic
        )

    @app.delete("/v1/platform/tenants/{tenant_id}")
    def delete_clinic(
        tenant_id: UUID,
        command: Versioned,
        request: Request,
        ctx: PortalContext = Depends(platform_context),
    ) -> dict[str, Any]:
        keyed(request, command)
        return PlatformAdmin(ctx).delete_clinic(command, tenant_id)

    @app.delete("/v1/platform/users/{user_id}")
    def delete_platform_user(
        user_id: UUID,
        command: Mutation,
        request: Request,
        ctx: PortalContext = Depends(platform_context),
    ) -> dict[str, Any]:
        keyed(request, command)
        return PlatformAdmin(ctx).delete_user(command, user_id)

    @app.post("/v1/platform/tenants")
    def create_tenant(
        command: TenantDraft, request: Request, ctx: PortalContext = Depends(platform_context)
    ) -> dict[str, Any]:
        keyed(request, command)
        return PlatformAdmin(ctx).save_tenant(command)

    @app.patch("/v1/platform/tenants/{tenant_id}")
    def update_tenant(
        tenant_id: UUID,
        command: TenantDraft,
        request: Request,
        ctx: PortalContext = Depends(platform_context),
    ) -> dict[str, Any]:
        keyed(request, command)
        return PlatformAdmin(ctx).save_tenant(command, tenant_id)

    @app.post("/v1/platform/tenants/{tenant_id}/administrators", status_code=202)
    def invite_administrator(
        tenant_id: UUID,
        command: InvitationDraft,
        request: Request,
        ctx: PortalContext = Depends(platform_context),
    ) -> dict[str, Any]:
        keyed(request, command)
        return invitations.activation_receipt(
            settings, PlatformAdmin(ctx).invite_administrator(command, tenant_id)
        )

    @app.post("/v1/platform/tenants/{tenant_id}/invitations", status_code=202)
    def platform_invite(
        tenant_id: UUID,
        command: InvitationDraft,
        request: Request,
        ctx: PortalContext = Depends(platform_context),
    ) -> dict[str, Any]:
        keyed(request, command)
        return invitations.activation_receipt(
            settings, PlatformAdmin(ctx).invite_user(command, tenant_id)
        )

    @app.post("/v1/platform/operators/invitations", status_code=202)
    def platform_invite_superadmin(
        command: PlatformInvitationDraft,
        request: Request,
        ctx: PortalContext = Depends(platform_context),
    ) -> dict[str, Any]:
        keyed(request, command)
        return PlatformAdmin(ctx).invite_superadmin(command)

    @app.get("/v1/platform/users")
    def platform_users(
        limit: int = Query(25, ge=1, le=100),
        cursor: str | None = Query(None, max_length=2048),
        search: str = Query("", max_length=254),
        ctx: PortalContext = Depends(platform_context),
    ) -> dict[str, Any]:
        return PlatformAdmin(ctx).users(limit, cursor, search.strip())

    @app.patch("/v1/platform/users/{user_id}/profile")
    def platform_user_profile(
        user_id: UUID,
        command: PlatformUserProfile,
        request: Request,
        ctx: PortalContext = Depends(platform_context),
    ) -> dict[str, Any]:
        keyed(request, command)
        return PlatformAdmin(ctx).save_user_profile(command, user_id)

    @app.get("/v1/platform/users/{user_id}/photo", response_class=Response)
    def platform_user_photo(
        user_id: UUID,
        ctx: PortalContext = Depends(platform_context),
    ) -> Response:
        return Response(PlatformAdmin(ctx).user_photo(user_id), media_type="image/jpeg")

    @app.put("/v1/platform/users/{user_id}/photo")
    def platform_save_user_photo(
        user_id: UUID,
        command: PlatformUserPhoto,
        request: Request,
        ctx: PortalContext = Depends(platform_context),
    ) -> dict[str, Any]:
        keyed(request, command)
        return PlatformAdmin(ctx).save_user_photo(command, user_id)

    @app.get("/v1/platform/tenants/{tenant_id}/permissions")
    def platform_clinic_permissions(
        tenant_id: UUID,
        limit: int = Query(50, ge=1, le=100),
        cursor: str | None = Query(None, max_length=2048),
        membership_id: UUID | None = None,
        ctx: PortalContext = Depends(platform_context),
    ) -> dict[str, Any]:
        return PlatformAdmin(ctx).clinic_permissions(tenant_id, limit, cursor, membership_id)

    @app.patch("/v1/platform/tenants/{tenant_id}/permissions/{membership_id}")
    def platform_save_clinic_permissions(
        tenant_id: UUID,
        membership_id: UUID,
        command: MembershipDraft,
        request: Request,
        ctx: PortalContext = Depends(platform_context),
    ) -> dict[str, Any]:
        keyed(request, command)
        return PlatformAdmin(ctx).save_clinic_permissions(tenant_id, membership_id, command)

    @app.patch("/v1/platform/users/{user_id}")
    def platform_user_status(
        user_id: UUID,
        command: PlatformUserStatus,
        request: Request,
        ctx: PortalContext = Depends(platform_context),
    ) -> dict[str, Any]:
        keyed(request, command)
        return PlatformAdmin(ctx).set_user_status(command, user_id)

    @app.api_route("/v1/platform/break-glass", methods=["GET", "POST"], include_in_schema=False)
    @app.get("/v1/platform/break-glass/{request_id}/appointment", include_in_schema=False)
    def retired_platform_access(request_id: UUID | None = None) -> None:
        raise PortalError("not_found", 404)

    for route in app.routes:
        if (
            isinstance(route, APIRoute)
            and not route.path.startswith("/v1/auth/")
            and (route.methods or set()) & {"POST", "PATCH", "PUT", "DELETE"}
        ):
            route.openapi_extra = {
                "parameters": [
                    {
                        "in": "header",
                        "name": "Idempotency-Key",
                        "required": True,
                        "schema": {"type": "string", "minLength": 8, "maxLength": 128},
                    }
                ]
            }
