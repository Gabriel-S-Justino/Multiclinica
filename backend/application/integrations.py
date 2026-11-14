from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import httpx
from sqlalchemy import func, select, text

from backend.application.portal_access import PortalContext, PortalError
from backend.application.portal_commands import (
    ChannelProvisionDraft,
    DeliveryDraft,
    IntegrationDraft,
)
from backend.infrastructure.fields import seal, unseal
from backend.infrastructure.messaging_models import (
    Dispatch,
    MessagingChannel,
    MessagingSession,
    WorkerHeartbeat,
)
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
    "ai": {
        "api_key",
        "provider",
        "model",
        "enabled",
        "data_policy_reference",
        "contract_reference",
        "monthly_tokens",
        "conversation_tokens",
    },
}
AI_CREDENTIALS = {"api_key", "provider", "model"}
AI_POLICY = {"data_policy_reference", "contract_reference", "monthly_tokens", "conversation_tokens"}
SECRET_FIELDS = {"access_token", "app_secret", "api_key"}
# O token de verificação do webhook é gerado pelo servidor e mostrado ao dono para ser
# colado na Meta; não dá acesso a nada além do aperto de mão do webhook.
METADATA_FIELDS = {
    "whatsapp": {"phone_number_id", "account_id", "graph_version", "queue_id", "verify_token"},
    "ai": {"provider", "model", "enabled", *AI_POLICY},
}
# Versão da Graph API usada quando a clínica não informa outra.
DEFAULT_GRAPH_VERSION = "v25.0"
WORKER_ONLINE_WINDOW = timedelta(minutes=2)
FAILURE_WINDOW = timedelta(days=7)


def appsecret_proof(access_token: str, app_secret: str) -> str:
    """Prova exigida pela Meta que confirma, numa só chamada, o token e o segredo do app."""
    return hmac.new(app_secret.encode(), access_token.encode(), hashlib.sha256).hexdigest()


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

    def _health(self, channel: MessagingChannel | None, moment: datetime) -> dict[str, Any]:
        seen = self.db.scalar(select(func.max(WorkerHeartbeat.seen_at)))
        failures: dict[str, int] = {}
        if channel is not None:
            failures = {
                str(code): int(total)
                for code, total in self.db.execute(
                    select(Dispatch.error_code, func.count())
                    .join(MessagingSession, MessagingSession.id == Dispatch.session_id)
                    .where(
                        Dispatch.tenant_id == self.ctx.tenant_id,
                        MessagingSession.channel_id == channel.id,
                        Dispatch.status.in_(("dead", "unknown", "failed")),
                        Dispatch.available_at >= moment - FAILURE_WINDOW,
                    )
                    .group_by(Dispatch.error_code)
                ).tuples()
            }
        return {
            "worker_online": bool(seen and moment - seen <= WORKER_ONLINE_WINDOW),
            "worker_seen_at": seen.isoformat() if seen else None,
            "last_event_at": channel.last_event_at.isoformat()
            if channel and channel.last_event_at
            else None,
            "webhook_verified_at": channel.webhook_verified_at.isoformat()
            if channel and channel.webhook_verified_at
            else None,
            "failed_deliveries": sum(failures.values()),
            "credentials_rejected": bool(failures.get("provider_unauthorized")),
        }

    def list(self) -> dict[str, Any]:
        moment = self.ctx.admin()
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
            required = AI_CREDENTIALS if provider == "ai" else PROVIDER_FIELDS[provider]
            complete = all(values.get(key) for key in required)
            verified = bool(row and row.verified_version == row.version)
            metadata = {key: values[key] for key in METADATA_FIELDS[provider] if key in values}
            # Etapas na ordem em que o dono as conclui; cada uma informa se já está pronta.
            steps: list[tuple[str, bool]] = [("fill_credentials", complete)]
            steps.append(("verify_credentials", verified))
            if provider == "whatsapp":
                mismatch = bool(
                    channel
                    and (
                        values.get("phone_number_id") != channel.phone_number_id
                        or values.get("account_id") != channel.account_id
                        or values.get("queue_id") != str(channel.default_queue_id)
                    )
                )
                steps.append(("provision_channel", channel is not None and not mismatch))
                if mismatch:
                    steps.append(("channel_mismatch", False))
                steps.append(
                    (
                        "verify_meta",
                        bool(channel and (channel.webhook_verified_at or channel.last_event_at)),
                    )
                )
                steps.append(("enable_delivery", bool(channel and channel.send_enabled)))
            else:
                steps.append(("approve_data_policy", all(values.get(key) for key in AI_POLICY)))
                steps.append(("enable_ai_adapter", values.get("enabled") == "true"))
            response.append(
                {
                    "provider": provider,
                    "configured": row is not None,
                    "version": row.version if row else 0,
                    "updated_at": row.updated_at.isoformat() if row else None,
                    "verification_status": "verified" if verified else "not_verified",
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
                    "pending_steps": [code for code, done in steps if not done],
                    "steps": [{"code": code, "done": done} for code, done in steps],
                    "health": self._health(channel, moment) if provider == "whatsapp" else None,
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
            if values.get("enabled", "false") not in {"true", "false"}:
                raise PortalError("invalid_integration_fields", 422)
            limits = [
                values.get(name, "4096") for name in ("conversation_tokens", "monthly_tokens")
            ]
            if any(not re.fullmatch(r"[0-9]{1,10}", limit) for limit in limits):
                raise PortalError("invalid_integration_fields", 422)
            if not 4096 <= int(limits[0]) <= int(limits[1]) <= 1_000_000_000:
                raise PortalError("invalid_integration_fields", 422)
            if values.get("enabled") == "true" and not all(
                values.get(key, "").strip() for key in AI_CREDENTIALS | AI_POLICY
            ):
                raise PortalError("integration_incomplete", 409)

    def save(self, provider: str, command: IntegrationDraft) -> dict[str, Any]:
        moment = self.ctx.admin(write=True)
        if (
            provider not in PROVIDER_FIELDS
            or not set(command.credentials) <= PROVIDER_FIELDS[provider]
        ):
            raise PortalError("invalid_integration_fields", 422)
        for key, value in command.credentials.items():
            raw = value.get_secret_value()
            if not raw.strip() or len(raw) > 4096 or not raw.isprintable():
                raise PortalError("invalid_integration_fields", 422)
            if key in SECRET_FIELDS and (len(raw) < 12 or not raw.isascii()):
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
        if provider == "whatsapp":
            # O dono não precisa escolher a versão da API nem inventar o token do webhook.
            values.setdefault("graph_version", DEFAULT_GRAPH_VERSION)
            values.setdefault("verify_token", token())
        self._validate_values(provider, values)
        if (
            provider == "whatsapp"
            and values != previous
            and self.db.scalar(
                select(MessagingChannel.id).where(
                    MessagingChannel.tenant_id == self.ctx.tenant_id,
                    MessagingChannel.send_enabled.is_(True),
                )
            )
        ):
            raise PortalError("pause_delivery_first", 409)
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
        # O número só é vinculado depois que a Meta confirmou que ele pertence à conta
        # informada: impede que uma clínica bloqueie o número de outra.
        if row.verified_version != row.version:
            raise PortalError("verification_required", 409)
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

    def _get(self, url: str, headers: dict[str, str], params: dict[str, str] | None) -> Any:
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
        try:
            return result.json()
        except ValueError:
            raise PortalError("provider_verification_failed", 409) from None

    def verify(self, provider: str) -> dict[str, str]:
        """Confere as credenciais no provedor e registra a verificação desta versão."""
        moment = self.ctx.validate(roles={"admin"}, recent=True)
        if provider not in PROVIDER_FIELDS:
            raise PortalError("invalid_integration_fields", 422)
        row = self._config(provider)
        values = self._values(row, provider)
        required = AI_CREDENTIALS if provider == "ai" else PROVIDER_FIELDS[provider]
        if row is None or not all(values.get(key) for key in required):
            raise PortalError("integration_incomplete", 409)
        self._validate_values(provider, values)
        if provider == "whatsapp":
            base = f"https://graph.facebook.com/{values['graph_version']}"
            headers = {"Authorization": f"Bearer {values['access_token']}"}
            proof = appsecret_proof(values["access_token"], values["app_secret"])
            # 1) O token e o segredo do app são válidos (a Meta recusa uma prova inválida).
            self._get(
                f"{base}/{values['phone_number_id']}",
                headers,
                {"fields": "id,display_phone_number,verified_name", "appsecret_proof": proof},
            )
            # 2) O número pertence à conta do WhatsApp Business informada.
            numbers = self._get(
                f"{base}/{values['account_id']}/phone_numbers",
                headers,
                {"fields": "id", "limit": "100", "appsecret_proof": proof},
            )
            listed = {
                str(item.get("id"))
                for item in (numbers.get("data") if isinstance(numbers, dict) else None) or []
                if isinstance(item, dict)
            }
            if values["phone_number_id"] not in listed:
                raise PortalError("phone_not_in_account", 409)
        else:
            self._get(
                f"https://api.openai.com/v1/models/{values['model']}",
                {"Authorization": f"Bearer {values['api_key']}"},
                None,
            )
        row.verified_version, row.verified_at = row.version, moment
        self.ctx.audit(f"integration.{provider}_verified", row.id)
        return {"provider": provider, "status": "credentials_verified"}

    def set_delivery(self, command: DeliveryDraft) -> dict[str, Any]:
        """Ativa ou pausa o envio de mensagens pelo WhatsApp da clínica."""
        self.ctx.admin(write=True)
        replay = self.ctx.replay("integration.whatsapp.delivery", command)
        if replay is not None:
            return replay
        channel = self.db.scalar(
            select(MessagingChannel).where(MessagingChannel.tenant_id == self.ctx.tenant_id)
        )
        if channel is None:
            raise PortalError("channel_unavailable", 409)
        if command.enabled:
            row = self._config("whatsapp")
            values = self._values(row, "whatsapp")
            if (
                row is None
                or row.verified_version != row.version
                or values.get("phone_number_id") != channel.phone_number_id
                or values.get("account_id") != channel.account_id
                or values.get("queue_id") != str(channel.default_queue_id)
            ):
                raise PortalError("verification_required", 409)
            if not (channel.webhook_verified_at or channel.last_event_at):
                raise PortalError("webhook_not_verified", 409)
        changed = self.db.scalar(
            text("SELECT public.set_clinic_whatsapp_delivery(:channel, :enabled)"),
            {"channel": channel.id, "enabled": command.enabled},
        )
        if not changed:
            raise PortalError("delivery_unavailable", 409)
        self.ctx.audit(
            "messaging.delivery_enabled" if command.enabled else "messaging.delivery_paused",
            channel.id,
        )
        return self.ctx.save(
            "integration.whatsapp.delivery", command, {"send_enabled": command.enabled}
        )
