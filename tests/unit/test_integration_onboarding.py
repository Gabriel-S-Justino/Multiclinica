"""Synthetic regression tests for integration onboarding; no provider network calls."""

import secrets
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import Select

from backend.application.integrations import Integrations
from backend.application.portal_access import PortalError
from backend.application.portal_commands import IntegrationDraft
from backend.config import Settings
from backend.infrastructure.fields import unseal
from backend.infrastructure.portal_models import IntegrationConfig, ServiceQueue


class FakeDB:
    def __init__(self, tenant_id):
        self.rows: list[IntegrationConfig] = []
        self.tenant_id = tenant_id
        self.queue = ServiceQueue(
            id=uuid4(),
            tenant_id=tenant_id,
            name="synthetic queue",
            kind="general",
            active=True,
            hours=[],
            outside_hours_notice="offline",
            version=1,
        )

    def get(self, model, row_id):
        if model is ServiceQueue and row_id == self.queue.id:
            return self.queue
        return None

    def scalars(self, statement):
        if "FROM integration_configs" in str(statement):
            return self.rows
        return []

    def scalar(self, statement, *_args):
        if isinstance(statement, Select) and "FROM integration_configs" in str(statement):
            return next(iter(self.rows), None)
        return None

    def add(self, row):
        if isinstance(row, IntegrationConfig) and row not in self.rows:
            self.rows.append(row)


def new_context():
    tenant_id = uuid4()
    db = FakeDB(tenant_id)
    settings = Settings(
        app_env="test",
        database_url=SecretStr("postgresql+psycopg://test:unused@localhost/test"),
        public_origin="https://example.invalid",
        token_key=SecretStr(secrets.token_hex(40)),
        field_key=SecretStr(Fernet.generate_key().decode()),
    )
    ctx = SimpleNamespace(
        tenant_id=tenant_id,
        db=db,
        settings=settings,
        admin=lambda **_kwargs: datetime.now(UTC),
        replay=lambda *_args: None,
        audit=lambda *_args: None,
        save=lambda _op, _command, result, *_args: result,
    )
    return ctx


def test_credential_settings_are_sealed_and_never_exposed():
    ctx = new_context()
    integration = Integrations(ctx)
    values = {
        "phone_number_id": "1234567890",
        "account_id": "9876543210",
        "graph_version": "v25.0",
        "queue_id": str(ctx.db.queue.id),
        "access_token": "synthetic-access-token-012345",
        "app_secret": "synthetic-app-secret-012345",  # pragma: allowlist secret (fixture sintética)
        "verify_token": "synthetic-verify-token-012345",  # pragma: allowlist secret (fixture sintética)
    }
    result = integration.save(
        "whatsapp", IntegrationDraft(version=0, idempotency_key=str(uuid4()), credentials=values)
    )
    assert result["configured"]
    row = ctx.db.rows[0]
    assert values["access_token"] not in row.credentials_ciphertext
    exposed = integration.list()["items"]
    whatsapp = next(item for item in exposed if item["provider"] == "whatsapp")
    assert whatsapp["setup_complete"]
    assert whatsapp["metadata"]["phone_number_id"] == values["phone_number_id"]
    assert whatsapp["metadata"]["queue_id"] == values["queue_id"]
    assert whatsapp["channel_id"] is None
    assert whatsapp["send_enabled"] is False
    assert "provision_channel" in whatsapp["pending_steps"]
    assert values["access_token"] not in str(exposed)
    assert values["app_secret"] not in str(exposed)
    # O token do webhook é mostrado ao dono para ser colado na Meta.
    assert whatsapp["metadata"]["verify_token"] == values["verify_token"]
    assert whatsapp["verification_status"] == "not_verified"
    assert [step["code"] for step in whatsapp["steps"]] == [
        "fill_credentials",
        "verify_credentials",
        "provision_channel",
        "verify_meta",
        "enable_delivery",
    ]
    assert whatsapp["steps"][0]["done"] and not whatsapp["steps"][1]["done"]


def test_whatsapp_defaults_api_version_and_webhook_token():
    ctx = new_context()
    integration = Integrations(ctx)
    values = {
        "phone_number_id": "1234567890",
        "account_id": "9876543210",
        "queue_id": str(ctx.db.queue.id),
        "access_token": "synthetic-access-token-012345",
        "app_secret": "synthetic-app-secret-012345",  # pragma: allowlist secret (fixture sintética)
    }
    integration.save(
        "whatsapp", IntegrationDraft(version=0, idempotency_key=str(uuid4()), credentials=values)
    )
    whatsapp = next(item for item in integration.list()["items"] if item["provider"] == "whatsapp")
    assert whatsapp["setup_complete"]
    assert whatsapp["metadata"]["graph_version"] == "v25.0"
    assert len(whatsapp["metadata"]["verify_token"]) >= 20


def test_metadata_update_preserves_existing_secrets():
    ctx = new_context()
    integration = Integrations(ctx)
    initial = {
        "provider": "openai",
        "model": "synthetic-model",
        "api_key": "synthetic-api-token-000000",  # pragma: allowlist secret (fixture sintética)
    }
    integration.save(
        "ai", IntegrationDraft(version=0, idempotency_key=str(uuid4()), credentials=initial)
    )
    integration.save(
        "ai",
        IntegrationDraft(
            version=1, idempotency_key=str(uuid4()), credentials={"model": "next-model"}
        ),
    )
    row = ctx.db.rows[0]
    values = unseal(
        ctx.settings, ctx.tenant_id, "integration", row.id, "ai", row.credentials_ciphertext
    )
    assert "synthetic-api-token-000000" in values
    exposed = integration.list()["items"]
    ai = next(item for item in exposed if item["provider"] == "ai")
    assert ai["metadata"]["model"] == "next-model"
    assert ai["setup_complete"] is True
    assert ai["pending_steps"] == [
        "verify_credentials",
        "approve_data_policy",
        "enable_ai_adapter",
    ]
    assert "synthetic-api-token-000000" not in str(exposed)


def test_custom_provider_verifies_model_and_requires_own_key_on_switch(monkeypatch):
    ctx = new_context()
    ctx.validate = ctx.admin
    ctx.settings.ai_extra_endpoints = {"clinica": "https://gateway.example/v1/"}
    service = Integrations(ctx)

    def save(version, **credentials):
        return service.save(
            "ai",
            IntegrationDraft(
                version=version, idempotency_key=str(uuid4()), credentials=credentials
            ),
        )

    save(0, provider="openai", model="prior", api_key=secrets.token_hex(16))
    with pytest.raises(PortalError):
        save(1, provider="clinica", model="empresa/modelo:teste")
    new_key = secrets.token_hex(16)
    save(1, provider="clinica", model="empresa/modelo:teste", api_key=new_key)
    item = next(item for item in service.list()["items"] if item["provider"] == "ai")
    assert "clinica" in item["ai_providers"]
    assert new_key not in str(item)
    content = '{"intent":"menu","confidence":1,"needs_clarification":false}'

    def respond(self, url, *, headers, json):
        assert url == "https://gateway.example/v1/chat/completions"
        assert headers["Authorization"] == "Bearer " + new_key
        assert json["model"] in {"empresa/modelo:teste", "incompatible"}
        assert json["messages"][-1]["content"] == "Voltar ao menu"
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={"choices": [{"message": {"content": content}}], "usage": {"total_tokens": 42}},
        )

    monkeypatch.setattr(httpx.Client, "post", respond)
    assert service.verify("ai")["status"] == "credentials_verified"
    save(2, model="incompatible")
    content = "invalid"
    with pytest.raises(PortalError):
        service.verify("ai")
    assert ctx.db.rows[0].verified_version != ctx.db.rows[0].version
