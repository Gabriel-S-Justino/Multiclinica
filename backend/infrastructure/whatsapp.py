"""Cloud API boundary. No logging of provider bodies, recipients or credentials."""

import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from typing import Any, Protocol

import httpx


class ProviderFailure(Exception):
    def __init__(self, code: str, *, retryable: bool = False, ambiguous: bool = False):
        self.code, self.retryable, self.ambiguous = code, retryable, ambiguous
        super().__init__(code)


class WhatsAppProvider(Protocol):
    def send_text(self, destination: str, text: str) -> str: ...


def verify_signature(raw: bytes, signature: str, app_secret: str) -> bool:
    expected = "sha256=" + hmac.new(app_secret.encode(), raw, hashlib.sha256).hexdigest()
    return bool(app_secret) and hmac.compare_digest(expected, signature)


@dataclass(frozen=True)
class CloudAPI:
    phone_number_id: str
    graph_version: str
    access_token: str

    def send_text(self, destination: str, text: str) -> str:
        if not re.fullmatch(r"v[0-9]{1,3}\.0", self.graph_version) or not re.fullmatch(
            r"[0-9]{1,80}", self.phone_number_id
        ):
            raise ProviderFailure("provider_configuration")
        if not re.fullmatch(r"\+[1-9][0-9]{7,14}", destination) or not 1 <= len(text) <= 4000:
            raise ProviderFailure("invalid_message")
        try:
            # Fixed hostname, TLS verification, bounded timeouts, no redirects/env proxies.
            with httpx.Client(
                timeout=httpx.Timeout(10, connect=5), follow_redirects=False, trust_env=False
            ) as client:
                response = client.post(
                    f"https://graph.facebook.com/{self.graph_version}/{self.phone_number_id}/messages",
                    headers={"Authorization": f"Bearer {self.access_token}"},
                    json={
                        "messaging_product": "whatsapp",
                        "to": destination[1:],
                        "type": "text",
                        "text": {"body": text, "preview_url": False},
                    },
                )
        except httpx.HTTPError:
            raise ProviderFailure("delivery_unknown", ambiguous=True) from None
        if response.status_code == 429:
            raise ProviderFailure("provider_throttled", retryable=True)
        if response.status_code >= 500:
            raise ProviderFailure("delivery_unknown", ambiguous=True)
        if response.status_code != 200:
            raise ProviderFailure("provider_rejected")
        try:
            payload: Any = json.loads(response.content)
            result = payload["messages"][0]["id"]
            if not isinstance(result, str) or not 1 <= len(result) <= 180:
                raise ValueError
            return result
        except (ValueError, TypeError, KeyError, IndexError):
            raise ProviderFailure("delivery_unknown", ambiguous=True) from None
