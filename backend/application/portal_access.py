import json
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from pydantic import SecretStr
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from backend.application.portal_commands import Versioned
from backend.application.scheduling_commands import Mutation
from backend.config import Settings
from backend.domain.permissions import Principal
from backend.infrastructure.db import set_tenant
from backend.infrastructure.models import AuditLog, Membership, Tenant, User
from backend.infrastructure.portal_models import EntityVersion
from backend.infrastructure.scheduling_models import IdempotencyRecord
from backend.infrastructure.security import digest


class PortalError(Exception):
    def __init__(self, code: str = "not_found", status: int = 404) -> None:
        self.code, self.status = code, status
        super().__init__(code)


def now(db: Session) -> datetime:
    result = db.scalar(select(func.clock_timestamp()))
    if not isinstance(result, datetime):
        raise PortalError("unavailable", 503)
    return result.astimezone(UTC)


def json_value(value: Any) -> str:
    if isinstance(value, SecretStr):
        return value.get_secret_value()
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    raise TypeError("Tipo não suportado no contrato")


class PortalContext:
    def __init__(
        self,
        db: Session,
        settings: Settings,
        identity: Principal,
        correlation_id: UUID | None = None,
        *,
        administrative_tenant_id: UUID | None = None,
    ) -> None:
        self.db, self.settings, self.identity = db, settings, identity
        self.correlation_id = correlation_id or uuid4()
        self.administrative_tenant_id = administrative_tenant_id

    @property
    def tenant_id(self) -> UUID:
        return self.administrative_tenant_id or self.identity.tenant_id

    def validate(
        self, *, lock: bool = False, roles: set[str] | None = None, recent: bool = False
    ) -> datetime:
        if self.administrative_tenant_id is not None:
            raise PortalError("permission_denied", 403)
        set_tenant(self.db, self.tenant_id)
        self.db.execute(
            text("SELECT set_config('app.user_id',:u,true)"), {"u": str(self.identity.user_id)}
        )
        if lock:
            self.db.execute(
                text("SELECT public.lock_schedule(:tenant)"), {"tenant": self.tenant_id}
            )
        member = self.db.scalar(
            select(Membership)
            .where(Membership.id == self.identity.membership_id)
            .execution_options(populate_existing=True)
        )
        user = self.db.scalar(
            select(User)
            .where(User.id == self.identity.user_id)
            .execution_options(populate_existing=True)
        )
        tenant = self.db.scalar(
            select(Tenant)
            .where(Tenant.id == self.tenant_id)
            .execution_options(populate_existing=True)
        )
        if (
            not member
            or not member.active
            or member.user_id != self.identity.user_id
            or member.tenant_id != self.tenant_id
            or member.role != self.identity.role
            or not user
            or not user.active
            or not tenant
            or not tenant.active
            or (roles is not None and member.role not in roles)
            or (self.settings.mfa_required and not self.identity.mfa_verified)
        ):
            raise PortalError("permission_denied", 403)
        moment = now(self.db)
        if recent and (
            not self.identity.mfa_verified
            or self.identity.authenticated_at is None
            or moment - self.identity.authenticated_at > timedelta(minutes=15)
        ):
            raise PortalError("reauthentication_required", 403)
        return moment

    def admin(self, *, write: bool = False) -> datetime:
        return self.validate(lock=write, roles={"admin"}, recent=write)

    def audit(
        self, action: str, resource_id: UUID | None = None, *, tenant_id: UUID | None = None
    ) -> None:
        self.db.add(
            AuditLog(
                tenant_id=tenant_id or self.tenant_id,
                actor_id=self.identity.user_id,
                action=action,
                resource_id=resource_id,
                correlation_id=self.correlation_id,
            )
        )

    def fingerprint(self, command: Mutation, target: UUID | str | None) -> str:
        raw = json.dumps(
            {
                "target": str(target) if target is not None else None,
                "command": command.model_dump(),
            },
            sort_keys=True,
            separators=(",", ":"),
            default=json_value,
        )
        return digest(self.settings, "portal-request", raw)

    def replay(
        self, operation: str, command: Mutation, target: UUID | str | None = None
    ) -> dict[str, Any] | None:
        row = self.db.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.tenant_id == self.tenant_id,
                IdempotencyRecord.key == command.idempotency_key,
            )
        )
        if row:
            if (
                row.actor_id != self.identity.user_id
                or row.operation != operation
                or row.request_hash != self.fingerprint(command, target)
            ):
                raise PortalError("idempotency_conflict", 409)
            return dict(row.result)
        return None

    def save(
        self,
        operation: str,
        command: Mutation,
        result: dict[str, Any],
        target: UUID | str | None = None,
    ) -> dict[str, Any]:
        self.db.add(
            IdempotencyRecord(
                tenant_id=self.tenant_id,
                key=command.idempotency_key,
                actor_id=self.identity.user_id,
                operation=operation,
                request_hash=self.fingerprint(command, target),
                result=result,
            )
        )
        self.db.flush()
        return result

    def version(self, kind: str, entity_id: UUID) -> int:
        row = self.db.scalar(
            select(EntityVersion).where(
                EntityVersion.tenant_id == self.tenant_id,
                EntityVersion.entity_type == kind,
                EntityVersion.entity_id == entity_id,
            )
        )
        return row.version if row else 0

    def bump(self, kind: str, entity_id: UUID, expected: int) -> int:
        row = self.db.scalar(
            select(EntityVersion)
            .where(
                EntityVersion.tenant_id == self.tenant_id,
                EntityVersion.entity_type == kind,
                EntityVersion.entity_id == entity_id,
            )
            .with_for_update()
        )
        current = row.version if row else 0
        if expected != current:
            raise PortalError("version_conflict", 409)
        if row is None:
            row = EntityVersion(
                tenant_id=self.tenant_id, entity_type=kind, entity_id=entity_id, version=current
            )
            self.db.add(row)
        row.version = current + 1
        return row.version

    def entity(self, model: Any, entity_id: UUID) -> Any:
        row = self.db.scalar(
            select(model).where(model.tenant_id == self.tenant_id, model.id == entity_id)
        )
        if row is None:
            raise PortalError()
        return row


def command_values(command: Versioned) -> dict[str, Any]:
    return command.model_dump(exclude={"idempotency_key", "version"})
