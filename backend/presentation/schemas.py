from typing import Annotated
from uuid import UUID

from pydantic import Field, SecretStr, StringConstraints

from backend.application.contracts import Command

TextToken = Annotated[str, StringConstraints(min_length=20, max_length=128)]


class Login(Command):
    login: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class VerifyMFA(Command):
    challenge: TextToken
    code: str = Field(pattern=r"^\d{6}$")


class PasswordChange(Command):
    login: str = Field(min_length=3, max_length=254)
    current_password: SecretStr = Field(min_length=1, max_length=128)
    new_password: SecretStr = Field(min_length=12, max_length=128)
    code: str = Field(pattern=r"^\d{6}$")


class SelectMembership(Command):
    membership_id: UUID


class RecoveryRequest(Command):
    login: str = Field(min_length=3, max_length=254)


class RecoveryConfirm(Command):
    token: TextToken
    password: str = Field(min_length=12, max_length=128)
