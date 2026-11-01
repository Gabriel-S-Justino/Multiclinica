import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from cryptography.fernet import Fernet

from backend.config import Settings

PASSWORDS = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
DUMMY_HASH = PASSWORDS.hash(secrets.token_urlsafe(32))


def verify_password(encoded: str, password: str) -> bool:
    try:
        return PASSWORDS.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


def token() -> str:
    return secrets.token_urlsafe(32)


def digest(settings: Settings, purpose: str, value: str) -> str:
    return hmac.new(
        settings.token_key.get_secret_value().encode(),
        f"{purpose}:{value}".encode(),
        hashlib.sha256,
    ).hexdigest()


def cipher(settings: Settings) -> Fernet:
    return Fernet(settings.field_key.get_secret_value().encode())
