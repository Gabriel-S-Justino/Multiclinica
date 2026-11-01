import json
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from backend.application.portal_access import PortalContext, PortalError
from backend.application.portal_commands import IntegrationDraft
from backend.infrastructure.fields import seal
from backend.infrastructure.portal_models import IntegrationConfig

PROVIDER_FIELDS = {"whatsapp": {"access_token", "app_secret", "verify_token"}, "ai": {"api_key"}}


class Integrations:
    def __init__(self, ctx: PortalContext) -> None:
        self.ctx, self.db = ctx, ctx.db

    def list(self) -> dict[str, Any]:
        self.ctx.admin()
        rows = {
            row.provider: row
            for row in self.db.scalars(
                select(IntegrationConfig).where(IntegrationConfig.tenant_id == self.ctx.tenant_id)
            )
        }
        return {
            "items": [
                {
                    "provider": provider,
                    "configured": provider in rows,
                    "version": rows[provider].version if provider in rows else 0,
                    "updated_at": rows[provider].updated_at.isoformat()
                    if provider in rows
                    else None,
                    "verification_status": "not_verified",
                }
                for provider in PROVIDER_FIELDS
            ]
        }

    def save(self, provider: str, command: IntegrationDraft) -> dict[str, Any]:
        moment = self.ctx.admin(write=True)
        if provider not in PROVIDER_FIELDS or set(command.credentials) != PROVIDER_FIELDS[provider]:
            raise PortalError("invalid_integration_fields", 422)
        if any(
            not value.get_secret_value()
            or len(value.get_secret_value()) > 4096
            or not value.get_secret_value().isascii()
            or not value.get_secret_value().isprintable()
            for value in command.credentials.values()
        ):
            raise PortalError("invalid_integration_fields", 422)
        replay = self.ctx.replay("integration.save", command, provider)
        if replay is not None:
            return replay
        row = self.db.scalar(
            select(IntegrationConfig)
            .where(
                IntegrationConfig.tenant_id == self.ctx.tenant_id,
                IntegrationConfig.provider == provider,
            )
            .with_for_update()
        )
        if command.version != (row.version if row else 0):
            raise PortalError("version_conflict", 409)
        if row is None:
            row = IntegrationConfig(id=uuid4(), tenant_id=self.ctx.tenant_id, provider=provider)
            self.db.add(row)
        raw = json.dumps(
            {key: value.get_secret_value() for key, value in command.credentials.items()},
            sort_keys=True,
        )
        row.credentials_ciphertext = seal(
            self.ctx.settings, self.ctx.tenant_id, "integration", row.id, provider, raw
        )
        row.version, row.updated_at = command.version + 1, moment
        self.ctx.audit("integration.credentials_rotated", row.id)
        return self.ctx.save(
            "integration.save",
            command,
            {
                "provider": provider,
                "configured": True,
                "version": row.version,
                "verification_status": "not_verified",
            },
            provider,
        )
