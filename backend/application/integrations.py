from __future__ import annotations

import json
import re
from typing import Any
from uuid import UUID, uuid4

import httpx
from sqlalchemy import select, text

from backend.application.portal_access import PortalContext, PortalError
from backend.application.portal_commands import ChannelProvisionDraft, IntegrationDraft
from backend.infrastructure.fields import seal, unseal
from backend.infrastructure.messaging_models import MessagingChannel
from backend.infrastructure.portal_models import IntegrationConfig, ServiceQueue
from backend.infrastructure.security import PASSWORDS, token

# Non-secret integration settings are returned separately; secrets never leave the backend.
PROVIDER_FIELDS = {
    "whatsapp": {
        "access_token",
        "app_secret",
        "verify_token",
        "phone_number_id",
        "account_id",
        "graph_version",
        "queue_id",
    },
    "ai": {"api_key", "provider", "model"},
}
SECRET_FIELDS = {"access_token", "app_secret", "verify_token", "api_key"}
METADATA_FIELDS = {
    "whatsapp": {"phone_number_id", "account_id", "graph_version", "queue_id"},
    "ai": {"provider", "model"},
}


class Integrations:
    def __init__(self, ctx: PortalContext) -> None:
        self.ctx, self.db = ctx, ctx.db

    def _config(self, provider: str) -> IntegrationConfig | None:
        return self.db.scalar(
            select(IntegrationConfig).where(
                IntegrationConfig.tenant_id == self.ctx.tenant_id,
                IntegrationConfig.provider == provider,
            )
        )

    def _values(self, row: IntegrationConfig | None, provider: str) -> dict[str, str]:
        if row is None:
            return {}
        result = json.loads(
            unseal(
                self.ctx.settings,
                self.ctx.tenant_id,
                "integration",
                row.id,
                provider,
                row.credentials_ciphertext,
            )
        )
        if not isinstance(result, dict) or any(
            not isinstance(key, str) or not isinstance(value, str) for key, value in result.items()
        ):
            raise PortalError("invalid_integration_fields", 422)
        return result

    def list(self) -> dict[str, Any]:
        self.ctx.admin()
        channels = list(
            self.db.scalars(
                select(MessagingChannel).where(MessagingChannel.tenant_id == self.ctx.tenant_id)
            )
        )
        channel = channels[0] if channels else None
        rows = {
            row.provider: row
            for row in self.db.scalars(
                select(IntegrationConfig).where(IntegrationConfig.tenant_id == self.ctx.tenant_id)
            )
        }
        response: list[dict[str, Any]] = []
        for provider in PROVIDER_FIELDS:
            row = rows.get(provider)
            values = self._values(row, provider)
            complete = all(values.get(key) for key in PROVIDER_FIELDS[provider])
            metadata = {key: values[key] for key in METADATA_FIELDS[provider] if key in values}
            steps: list[str] = []
            if not complete:
                steps.append("fill_credentials")
            if provider == "whatsapp":
                if not channel:
                    steps.append("provision_channel")
                elif (
                    values.get("phone_number_id") != channel.phone_number_id
                    or values.get("account_id") != channel.account_id
                    or values.get("queue_id") != str(channel.default_queue_id)
                ):
                    steps.append("channel_mismatch")
                if not channel or not channel.send_enabled:
                    steps.append("enable_delivery")
                steps.append("configure_worker")
                steps.append("verify_meta")
            else:
                steps.append("enable_ai_adapter")
                steps.append("approve_data_policy")
            response.append(
                {
                    "provider": provider,
                    "configured": row is not None,
                    "version": row.version if row else 0,
                    "updated_at": row.updated_at.isoformat() if row else None,
                    "verification_status": "not_verified",
                    "setup_complete": complete,
                    "metadata": metadata,
                    "channel_id": str(channel.id) if provider == "whatsapp" and channel else None,
                    "webhook_url": (
                        f"{self.ctx.settings.public_origin}/v1/webhooks/whatsapp/{channel.id}"
                        if provider == "whatsapp" and channel
                        else None
                    ),
                    "send_enabled": bool(channel.send_enabled)
                    if provider == "whatsapp" and channel
                    else False,
                    "pending_steps": steps,
                }
            )
        return {"items": response}

    def _validate_values(self, provider: str, values: dict[str, str]) -> None:
        if provider == "whatsapp":
            for key in ("phone_number_id", "account_id"):
                if key in values and not re.fullmatch(r"[0-9]{1,80}", values[key]):
                    raise PortalError("invalid_integration_fields", 422)
            if "graph_version" in values and not re.fullmatch(
                r"v[0-9]{1,3}\.0", values["graph_version"]
            ):
                raise PortalError("invalid_integration_fields", 422)
            if "queue_id" in values:
                try:
                    queue_id = UUID(values["queue_id"])
                except ValueError:
                    raise PortalError("invalid_integration_fields", 422) from None
                queue = self.db.get(ServiceQueue, queue_id)
                if not queue or queue.tenant_id != self.ctx.tenant_id or not queue.active:
                    raise PortalError("queue_unavailable", 422)
            channel = self.db.scalar(
                select(MessagingChannel).where(MessagingChannel.tenant_id == self.ctx.tenant_id)
            )
            if channel and any(
                key in values and values[key] != expected
                for key, expected in {
                    "phone_number_id": channel.phone_number_id,
                    "account_id": channel.account_id,
                    "queue_id": str(channel.default_queue_id),
                }.items()
            ):
                raise PortalError("channel_mismatch", 409)
        else:
            if "provider" in values and values["provider"] != "openai":
                raise PortalError("invalid_integration_fields", 422)
            if "model" in values and not re.fullmatch(r"[A-Za-z0-9._-]{1,120}", values["model"]):
                raise PortalError("invalid_integration_fields", 422)

    def save(self, provider: str, command: IntegrationDraft) -> dict[str, Any]:
        moment = self.ctx.admin(write=True)
        if (
            provider not in PROVIDER_FIELDS
            or not set(command.credentials) <= PROVIDER_FIELDS[provider]
        ):
            raise PortalError("invalid_integration_fields", 422)
        for key, value in command.credentials.items():
            raw = value.get_secret_value()
            if not raw or len(raw) > 4096 or not raw.isascii() or not raw.isprintable():
                raise PortalError("invalid_integration_fields", 422)
            if key in SECRET_FIELDS and len(raw) < 12:
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
        previous = self._values(row, provider)
        provided = {key: value.get_secret_value() for key, value in command.credentials.items()}
        values = {**previous, **provided}
        self._validate_values(provider, values)
        if row is None:
            row = IntegrationConfig(id=uuid4(), tenant_id=self.ctx.tenant_id, provider=provider)
            self.db.add(row)
        row.credentials_ciphertext = seal(
            self.ctx.settings,
            self.ctx.tenant_id,
            "integration",
            row.id,
            provider,
            json.dumps(values, sort_keys=True),
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

    def provision_channel(self, command: ChannelProvisionDraft) -> dict[str, Any]:
        self.ctx.admin(write=True)
        replay = self.ctx.replay("integration.whatsapp.provision", command)
        if replay is not None:
            return replay
        row = self._config("whatsapp")
        if row is None or command.version != row.version:
            raise PortalError("version_conflict", 409)
        values = self._values(row, "whatsapp")
        if not all(values.get(key) for key in PROVIDER_FIELDS["whatsapp"]):
            raise PortalError("integration_incomplete", 409)
        self._validate_values("whatsapp", values)
        if self.db.scalar(
            select(MessagingChannel.id).where(MessagingChannel.tenant_id == self.ctx.tenant_id)
        ):
            raise PortalError("channel_already_exists", 409)
        # A narrowly scoped, owner-installed DB function is required here.
        # clinic_runtime never receives unrestricted INSERT rights on users.
        result = self.db.scalar(
            text(
                "SELECT public.provision_clinic_whatsapp_channel("
                ":tenant_id,:queue_id,:phone_id,:account_id,:graph_version,:password_hash)"
            ),
            {
                "tenant_id": self.ctx.tenant_id,
                "queue_id": UUID(values["queue_id"]),
                "phone_id": values["phone_number_id"],
                "account_id": values["account_id"],
                "graph_version": values["graph_version"],
                "password_hash": PASSWORDS.hash(token()),
            },
        )
        if not isinstance(result, UUID):
            raise PortalError("channel_provision_failed", 503)
        self.ctx.audit("messaging.channel_provisioned", result)
        return self.ctx.save(
            "integration.whatsapp.provision",
            command,
            {
                "channel_id": str(result),
                "webhook_url": (f"{self.ctx.settings.public_origin}/v1/webhooks/whatsapp/{result}"),
                "send_enabled": False,
            },
        )

    def verify(self, provider: str) -> dict[str, str]:
        # Test only metadata/key access. This does not activate WhatsApp sends or AI.
        self.ctx.validate(roles={"admin"}, recent=True)
        if provider not in PROVIDER_FIELDS:
            raise PortalError("invalid_integration_fields", 422)
        values = self._values(self._config(provider), provider)
        if not all(values.get(key) for key in PROVIDER_FIELDS[provider]):
            raise PortalError("integration_incomplete", 409)
        if provider == "whatsapp":
            self._validate_values(provider, values)
            url = (
                f"https://graph.facebook.com/{values['graph_version']}/{values['phone_number_id']}"
            )
            headers = {"Authorization": f"Bearer {values['access_token']}"}
            params = {"fields": "id,display_phone_number,verified_name"}
        else:
            self._validate_values(provider, values)
            url = f"https://api.openai.com/v1/models/{values['model']}"
            headers = {"Authorization": f"Bearer {values['api_key']}"}
            params = None
        try:
            with httpx.Client(
                timeout=httpx.Timeout(8, connect=3),
                trust_env=False,
                follow_redirects=False,
            ) as client:
                result = client.get(url, headers=headers, params=params)
        except httpx.HTTPError:
            raise PortalError("provider_unavailable", 503) from None
        if result.status_code != 200:
            raise PortalError("provider_verification_failed", 409)
        return {
            "provider": provider,
            "status": "credentials_verified",
            "message": "Conexão de leitura verificada; o atendimento ainda não está ativado.",
        }
