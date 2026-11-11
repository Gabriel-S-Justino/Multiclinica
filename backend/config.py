from typing import Literal, Self
from urllib.parse import urlsplit
from uuid import UUID

from cryptography.fernet import Fernet
from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)
    app_env: Literal["local", "test", "staging", "production"] = "local"
    database_url: SecretStr
    public_origin: str
    token_key: SecretStr
    field_key: SecretStr
    mfa_required: bool = True
    staging_demo_user_id: UUID | None = None

    @field_validator("database_url")
    @classmethod
    def postgres_only(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().startswith("postgresql+psycopg://"):
            raise ValueError("PostgreSQL com psycopg é obrigatório")
        return value

    @field_validator("token_key")
    @classmethod
    def strong_key(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        if len(raw) < 64 or len(set(raw)) < 8 or raw.startswith("REPLACE_"):
            raise ValueError("Configure uma chave aleatória com pelo menos 64 caracteres")
        return value

    @field_validator("field_key")
    @classmethod
    def valid_cipher_key(cls, value: SecretStr) -> SecretStr:
        try:
            Fernet(value.get_secret_value().encode())
        except (ValueError, TypeError) as error:
            raise ValueError("Configure uma chave de cifra válida") from error
        return value

    @field_validator("public_origin")
    @classmethod
    def origin_only(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.path
            or parsed.query
            or parsed.fragment
            or parsed.username
        ):
            raise ValueError("A origem deve ser HTTPS e não conter caminho ou credenciais")
        return value

    @model_validator(mode="after")
    def require_mfa(self) -> Self:
        if self.app_env != "test" and not self.mfa_required:
            raise ValueError("MFA não pode ser desabilitado fora dos testes")
        if self.staging_demo_user_id is not None and self.app_env != "staging":
            raise ValueError("A conta de demonstração só pode ser configurada em staging")
        return self

    def requires_mfa_for(self, user_id: UUID) -> bool:
        demo_account = self.app_env == "staging" and self.staging_demo_user_id == user_id
        return self.mfa_required and not demo_account
