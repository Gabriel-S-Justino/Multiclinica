import hashlib
import hmac
import json
from uuid import uuid4

import httpx
import pytest

from backend.infrastructure.whatsapp import CloudAPI, ProviderFailure, verify_signature


def test_signature_is_over_exact_raw_bytes():
    material = uuid4().hex
    raw = b'{"message":"synthetic"}'
    signature = "sha256=" + hmac.new(material.encode(), raw, hashlib.sha256).hexdigest()
    assert verify_signature(raw, signature, material)
    assert not verify_signature(raw + b" ", signature, material)
    assert not verify_signature(raw, signature, uuid4().hex)


@pytest.mark.parametrize(
    "status,payload,error,retryable,ambiguous",
    [
        (200, {"messages": [{"id": "wamid-fixture"}]}, None, False, False),
        (200, {"messages": []}, "delivery_unknown", False, True),
        (429, {}, "provider_throttled", True, False),
        (500, {}, "delivery_unknown", False, True),
        (400, {}, "provider_rejected", False, False),
        (302, {}, "provider_rejected", False, False),
    ],
)
def test_cloud_adapter_fixed_endpoint_payload_and_failure_classification(
    monkeypatch, status, payload, error, retryable, ambiguous
):
    calls = []
    material = uuid4().hex

    class Client:
        def __init__(self, **options):
            assert options["follow_redirects"] is False and options["trust_env"] is False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, **kwargs):
            calls.append((url, kwargs))
            return httpx.Response(status, content=json.dumps(payload).encode())

    monkeypatch.setattr(httpx, "Client", Client)
    provider = CloudAPI("100", "v1.0", material)  # synthetic version, not a supported-version claim
    if error:
        with pytest.raises(ProviderFailure) as caught:
            provider.send_text("+15550000000", "Mensagem sintética")
        assert caught.value.code == error
        assert caught.value.retryable is retryable and caught.value.ambiguous is ambiguous
    else:
        assert provider.send_text("+15550000000", "Mensagem sintética") == "wamid-fixture"
    url, request = calls[0]
    assert url == "https://graph.facebook.com/v1.0/100/messages"
    assert request["json"]["text"]["preview_url"] is False
    assert request["json"]["to"] == "15550000000"


def test_network_error_is_ambiguous(monkeypatch):
    class Client:
        def __init__(self, **options):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, *args, **kwargs):
            raise httpx.ReadTimeout("synthetic")

    monkeypatch.setattr(httpx, "Client", Client)
    with pytest.raises(ProviderFailure) as caught:
        CloudAPI("100", "v1.0", uuid4().hex).send_text("+15550000000", "Mensagem sintética")
    assert caught.value.ambiguous and not caught.value.retryable


@pytest.mark.parametrize(
    "version,number,destination",
    [
        ("https://foreign.invalid", "100", "+15550000000"),
        ("v1.0", "../foreign", "+15550000000"),
        ("v1.0", "100", "https://foreign.invalid"),
    ],
)
def test_configuration_cannot_select_another_host_or_recipient_scheme(version, number, destination):
    with pytest.raises(ProviderFailure):
        CloudAPI(number, version, uuid4().hex).send_text(destination, "Mensagem sintética")
