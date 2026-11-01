import base64
import secrets
from uuid import UUID

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from backend.config import Settings


def field_cipher(settings: Settings) -> AESGCM:
    material = base64.urlsafe_b64decode(settings.field_key.get_secret_value())
    key = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=None, info=b"clinic/patient-fields/v1"
    ).derive(material)
    return AESGCM(key)


def associated_data(tenant_id: UUID, entity: str, row_id: UUID, field: str) -> bytes:
    return f"v1:{tenant_id}:{entity}:{row_id}:{field}".encode()


def seal(
    settings: Settings, tenant_id: UUID, entity: str, row_id: UUID, field: str, value: str
) -> str:
    nonce = secrets.token_bytes(12)
    data = field_cipher(settings).encrypt(
        nonce, value.encode(), associated_data(tenant_id, entity, row_id, field)
    )
    return "v1." + base64.urlsafe_b64encode(nonce + data).decode()


def unseal(
    settings: Settings, tenant_id: UUID, entity: str, row_id: UUID, field: str, value: str
) -> str:
    if not value.startswith("v1."):
        raise ValueError("Versão de chave não suportada")
    raw = base64.urlsafe_b64decode(value[3:])
    return (
        field_cipher(settings)
        .decrypt(raw[:12], raw[12:], associated_data(tenant_id, entity, row_id, field))
        .decode()
    )
