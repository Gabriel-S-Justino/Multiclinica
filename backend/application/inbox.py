from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select

from backend.application.pagination import cursor_for, offset_for
from backend.application.portal_access import PortalContext, PortalError, command_values
from backend.application.portal_commands import HandoffDraft, QueueDraft, ReplyDraft, Versioned
from backend.infrastructure.fields import seal, unseal
from backend.infrastructure.models import Tenant
from backend.infrastructure.portal_models import Handoff, Message, QueueMembership, ServiceQueue
from backend.infrastructure.scheduling_models import (
    Contact,
    Conversation,
    ConversationState,
    OutboxEvent,
)


class Inbox:
    def __init__(self, ctx: PortalContext) -> None:
        self.ctx, self.db = ctx, ctx.db

    def queue_ids(self) -> list[UUID]:
        if self.ctx.identity.role not in {"admin", "reception"}:
            return []
        return list(
            self.db.scalars(
                select(QueueMembership.queue_id).where(
                    QueueMembership.tenant_id == self.ctx.tenant_id,
                    QueueMembership.membership_id == self.ctx.identity.membership_id,
                )
            )
        )

    def queues(self, *, manage: bool = False) -> dict[str, Any]:
        self.ctx.admin() if manage else self.ctx.validate(roles={"admin", "reception"})
        query = select(ServiceQueue).where(ServiceQueue.tenant_id == self.ctx.tenant_id)
        if not manage:
            query = query.where(
                ServiceQueue.id.in_(self.queue_ids()), ServiceQueue.active.is_(True)
            )
        rows = self.db.scalars(query.order_by(ServiceQueue.name).limit(100))
        return {
            "items": [
                {
                    "id": str(row.id),
                    "name": row.name,
                    "kind": row.kind,
                    "active": row.active,
                    "hours": row.hours,
                    "outside_hours_notice": row.outside_hours_notice,
                    "version": row.version,
                }
                for row in rows
            ]
        }

    def save_queue(self, command: QueueDraft, entity_id: UUID | None = None) -> dict[str, Any]:
        self.ctx.admin(write=True)
        replay = self.ctx.replay("queue.save", command, entity_id)
        if replay is not None:
            return replay
        row: ServiceQueue = (
            self.ctx.entity(ServiceQueue, entity_id)
            if entity_id
            else ServiceQueue(id=uuid4(), tenant_id=self.ctx.tenant_id)
        )
        if command.version != (row.version if entity_id else 0):
            raise PortalError("version_conflict", 409)
        for key, value in command_values(command).items():
            setattr(row, key, value)
        row.version = command.version + 1
        self.db.add(row)
        self.ctx.audit("queue.saved", row.id)
        return self.ctx.save(
            "queue.save", command, {"id": str(row.id), "version": row.version}, entity_id
        )

    def _row(self, handoff_id: UUID, *, assigned: bool = False) -> Handoff:
        row = self.db.scalar(
            select(Handoff)
            .where(
                Handoff.tenant_id == self.ctx.tenant_id,
                Handoff.id == handoff_id,
                Handoff.queue_id.in_(self.queue_ids()),
            )
            .with_for_update()
        )
        if row is None:
            raise PortalError()
        if assigned and (
            row.status != "assigned"
            or row.assignee_membership_id != self.ctx.identity.membership_id
        ):
            raise PortalError("handoff_not_owned", 409)
        return row

    def list(self, limit: int, cursor: str | None) -> dict[str, Any]:
        self.ctx.validate(roles={"admin", "reception"})
        filters = {"limit": limit}
        offset = offset_for(self.ctx, cursor, "inbox", filters)
        rows = list(
            self.db.scalars(
                select(Handoff)
                .where(
                    Handoff.tenant_id == self.ctx.tenant_id,
                    Handoff.queue_id.in_(self.queue_ids()),
                    Handoff.status.in_(["waiting", "assigned"]),
                )
                .order_by(Handoff.created_at, Handoff.id)
                .offset(offset)
                .limit(limit + 1)
            )
        )
        return {
            "items": [self.describe(row) for row in rows[:limit]],
            "next_cursor": cursor_for(
                self.ctx, offset + limit if len(rows) > limit else None, "inbox", filters
            ),
        }

    def describe(self, row: Handoff) -> dict[str, Any]:
        queue: ServiceQueue = self.ctx.entity(ServiceQueue, row.queue_id)
        return {
            "id": str(row.id),
            "conversation_id": str(row.conversation_id),
            "queue_id": str(row.queue_id),
            "queue_name": queue.name,
            "reason_code": row.reason_code,
            "status": row.status,
            "version": row.version,
            "assigned_to_me": row.assignee_membership_id == self.ctx.identity.membership_id,
            "created_at": row.created_at.isoformat(),
        }

    def create(self, command: HandoffDraft) -> dict[str, Any]:
        moment = self.ctx.validate(lock=True, roles={"admin", "reception"})
        replay = self.ctx.replay("handoff.create", command)
        if replay is not None:
            return replay
        if command.queue_id not in self.queue_ids():
            raise PortalError()
        queue: ServiceQueue = self.ctx.entity(ServiceQueue, command.queue_id)
        if not queue.active or not queue.hours:
            raise PortalError("queue_unavailable", 409)
        self.ctx.entity(Contact, command.contact_id)
        conversations = list(
            self.db.scalars(
                select(Conversation).where(
                    Conversation.tenant_id == self.ctx.tenant_id,
                    Conversation.contact_id == command.contact_id,
                )
            )
        )
        conversation_ids = [item.id for item in conversations]
        existing = self.db.scalar(
            select(Handoff)
            .where(
                Handoff.tenant_id == self.ctx.tenant_id,
                Handoff.conversation_id.in_(conversation_ids),
                Handoff.status.in_(["waiting", "assigned"]),
            )
            .limit(1)
        )
        if existing:
            if existing.queue_id not in self.queue_ids():
                raise PortalError()
            return self.ctx.save("handoff.create", command, self.describe(existing))
        active = list(
            self.db.execute(
                select(Conversation, ConversationState)
                .join(
                    ConversationState,
                    (ConversationState.tenant_id == Conversation.tenant_id)
                    & (ConversationState.conversation_id == Conversation.id),
                )
                .where(
                    Conversation.tenant_id == self.ctx.tenant_id,
                    Conversation.contact_id == command.contact_id,
                    ConversationState.state != "DONE",
                )
                .with_for_update()
            )
        )
        if len(active) > 1:
            raise PortalError("conversation_conflict", 409)
        if active:
            conversation, state = active[0]
            state.state, state.version, state.context = "HUMAN_HANDOFF", state.version + 1, {}
        else:
            conversation = Conversation(
                id=uuid4(), tenant_id=self.ctx.tenant_id, contact_id=command.contact_id
            )
            self.db.add(conversation)
            self.db.flush()
            self.db.add(
                ConversationState(
                    tenant_id=self.ctx.tenant_id,
                    conversation_id=conversation.id,
                    state="HUMAN_HANDOFF",
                    version=0,
                    context={},
                )
            )
        row = Handoff(
            id=uuid4(),
            tenant_id=self.ctx.tenant_id,
            conversation_id=conversation.id,
            queue_id=queue.id,
            reason_code=command.reason_code,
            created_at=moment,
        )
        self.db.add(row)
        tenant = self.db.get(Tenant, self.ctx.tenant_id)
        local = moment.astimezone(ZoneInfo(tenant.timezone if tenant else "UTC"))
        minute = local.hour * 60 + local.minute
        in_hours = any(
            window["weekday"] == local.weekday()
            and window["start_minute"] <= minute < window["end_minute"]
            for window in queue.hours
        )
        self.ctx.audit("handoff.created", row.id)
        self.db.flush()
        return self.ctx.save(
            "handoff.create",
            command,
            self.describe(row)
            | {
                "within_hours": in_hours,
                "notice": None if in_hours else queue.outside_hours_notice,
            },
        )

    def act(self, command: Versioned, handoff_id: UUID, action: str) -> dict[str, Any]:
        self.ctx.validate(lock=True, roles={"admin", "reception"})
        replay = self.ctx.replay(f"handoff.{action}", command, handoff_id)
        if replay is not None:
            return replay
        row = self._row(handoff_id, assigned=action != "claim")
        if row.version != command.version:
            raise PortalError("version_conflict", 409)
        if action == "claim":
            if row.status != "waiting":
                raise PortalError("handoff_already_claimed", 409)
            row.status, row.assignee_membership_id = "assigned", self.ctx.identity.membership_id
        elif action in {"release", "close"}:
            row.status = "released" if action == "release" else "closed"
            state = self.db.scalar(
                select(ConversationState)
                .where(
                    ConversationState.tenant_id == self.ctx.tenant_id,
                    ConversationState.conversation_id == row.conversation_id,
                )
                .with_for_update()
            )
            if not state or state.state != "HUMAN_HANDOFF":
                raise PortalError("conversation_conflict", 409)
            state.state, state.version, state.context = (
                ("MENU" if action == "release" else "DONE"),
                state.version + 1,
                {},
            )
        else:
            raise PortalError()
        row.version += 1
        self.ctx.audit(f"handoff.{action}", row.id)
        return self.ctx.save(f"handoff.{action}", command, self.describe(row), handoff_id)

    def messages(self, handoff_id: UUID, limit: int, cursor: str | None) -> dict[str, Any]:
        self.ctx.validate(roles={"admin", "reception"})
        row = self._row(handoff_id)
        filters = {"handoff_id": str(handoff_id), "limit": limit}
        offset = offset_for(self.ctx, cursor, "messages", filters)
        rows = list(
            self.db.scalars(
                select(Message)
                .where(
                    Message.tenant_id == self.ctx.tenant_id,
                    Message.conversation_id == row.conversation_id,
                )
                .order_by(Message.created_at, Message.id)
                .offset(offset)
                .limit(limit + 1)
            )
        )
        return {
            "handoff": self.describe(row),
            "items": [
                {
                    "id": str(item.id),
                    "direction": item.direction,
                    "text": unseal(
                        self.ctx.settings,
                        self.ctx.tenant_id,
                        "message",
                        item.id,
                        "body",
                        item.body_ciphertext,
                    ),
                    "delivery_status": item.delivery_status,
                    "created_at": item.created_at.isoformat(),
                }
                for item in rows[:limit]
            ],
            "next_cursor": cursor_for(
                self.ctx, offset + limit if len(rows) > limit else None, "messages", filters
            ),
        }

    def reply(self, command: ReplyDraft, handoff_id: UUID) -> dict[str, Any]:
        moment = self.ctx.validate(lock=True, roles={"admin", "reception"})
        replay = self.ctx.replay("handoff.reply", command, handoff_id)
        if replay is not None:
            return replay
        row = self._row(handoff_id, assigned=True)
        if row.version != command.version:
            raise PortalError("version_conflict", 409)
        state = self.db.scalar(
            select(ConversationState).where(
                ConversationState.tenant_id == self.ctx.tenant_id,
                ConversationState.conversation_id == row.conversation_id,
            )
        )
        if not state or state.state != "HUMAN_HANDOFF":
            raise PortalError("conversation_conflict", 409)
        message_id = uuid4()
        self.db.add(
            Message(
                id=message_id,
                tenant_id=self.ctx.tenant_id,
                conversation_id=row.conversation_id,
                body_ciphertext=seal(
                    self.ctx.settings,
                    self.ctx.tenant_id,
                    "message",
                    message_id,
                    "body",
                    command.text,
                ),
                direction="outbound",
                delivery_status="queued",
                sender_user_id=self.ctx.identity.user_id,
                created_at=moment,
            )
        )
        self.db.add(
            OutboxEvent(
                tenant_id=self.ctx.tenant_id,
                event_key=f"message:{message_id}",
                event_type="message.send",
                aggregate_id=message_id,
                payload={
                    "message_id": str(message_id),
                    "conversation_id": str(row.conversation_id),
                },
                created_at=moment,
            )
        )
        row.version += 1
        self.ctx.audit("message.queued", message_id)
        return self.ctx.save(
            "handoff.reply",
            command,
            {"message_id": str(message_id), "delivery_status": "queued", "version": row.version},
            handoff_id,
        )
