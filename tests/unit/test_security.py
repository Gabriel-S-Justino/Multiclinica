import secrets
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError

from backend.config import Settings
from backend.domain.permissions import Principal, can_read_audit, can_read_professional
from backend.infrastructure.security import PASSWORDS, digest, verify_password


def settings(**overrides):
    values = {
        "database_url": "postgresql+psycopg://user:fake@localhost/test",  # pragma: allowlist secret (URL fictícia)
        "public_origin": "https://testserver",
        "token_key": secrets.token_hex(32),
        "field_key": Fernet.generate_key().decode(),
        "app_env": "test",
        "mfa_required": True,
    }
    return Settings(**(values | overrides))


@pytest.mark.parametrize(
    "overrides",
    [
        {"database_url": "sqlite://"},
        {"token_key": "short"},
        {"public_origin": "https://example.com/path"},
        {"public_origin": "http://example.com"},
        {"field_key": "invalid"},
        {"app_env": "local", "mfa_required": False},
        {"app_env": "staging", "mfa_required": False},
        {"app_env": "production", "mfa_required": False},
        {"app_env": "production", "staging_demo_user_id": uuid4()},
    ],
)
def test_configuration_fails_closed(overrides):
    with pytest.raises(ValidationError):
        settings(**overrides)


def test_staging_accepts_explicit_demo_configuration():
    demo = uuid4()
    config = settings(app_env="staging", staging_demo_user_id=demo)
    assert not config.requires_mfa_for(demo)
    assert config.requires_mfa_for(uuid4())


def test_password_and_token_storage():
    encoded = PASSWORDS.hash("a sufficiently long password")
    assert encoded.startswith("$argon2id$")
    assert verify_password(encoded, "a sufficiently long password")
    assert not verify_password(encoded, "incorrect")
    config = settings()
    assert digest(config, "session", "raw") != digest(config, "csrf", "raw")


@pytest.mark.parametrize(
    "role,own,assigned,allowed",
    [
        ("collaborator", True, False, True),
        ("collaborator", False, True, False),
        ("reception", False, True, True),
        ("reception", False, False, False),
        ("admin", False, False, True),
        ("superadmin", False, True, False),
    ],
)
def test_professional_permission_matrix(role, own, assigned, allowed):
    user_id = uuid4()
    identity = Principal(user_id, uuid4(), uuid4(), role, True)
    assert can_read_professional(identity, user_id if own else uuid4(), assigned) is allowed
    assert can_read_audit(identity) is (role == "admin")
