"""Controlled operator commands. Run with migration credentials, never from HTTP."""

import argparse
import getpass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pyotp
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.config import Settings
from backend.infrastructure.db import set_tenant
from backend.infrastructure.models import Membership, RecoveryToken, Tenant, User
from backend.infrastructure.portal_models import PlatformOperator
from backend.infrastructure.security import PASSWORDS, cipher, digest, token


def main() -> None:
    parser = argparse.ArgumentParser(description="Administração local controlada")
    parser.add_argument(
        "command", choices=["bootstrap", "bootstrap-platform", "provision-user", "issue-recovery"]
    )
    parser.add_argument("--login", required=True)
    parser.add_argument("--tenant-name")
    args = parser.parse_args()
    settings = Settings()
    # Never obtain privileged credentials from the runtime Settings object.
    import os

    url = os.environ.get("MIGRATION_DATABASE_URL")
    if not url:
        raise SystemExit("Configure MIGRATION_DATABASE_URL no processo de administração")
    engine = create_engine(url, hide_parameters=True)
    with Session(engine) as db, db.begin():
        user = db.scalar(select(User).where(User.login == args.login.lower()))
        if args.command in {"bootstrap", "bootstrap-platform", "provision-user"}:
            if user or (args.command == "bootstrap" and not args.tenant_name):
                raise SystemExit("Usuário já existe ou nome da clínica ausente")
            password = getpass.getpass("Senha (mínimo 12 caracteres): ")
            if len(password) < 12 or len(password) > 128:
                raise SystemExit("Senha inválida")
            # Operator enrolls the authenticator in person; no secret is printed.
            secret = getpass.getpass("Segredo TOTP provisionado ao autenticador: ").strip()
            code = getpass.getpass("Código atual do autenticador: ").strip()
            try:
                valid = pyotp.TOTP(secret).verify(code)
            except (ValueError, TypeError):
                valid = False
            if not valid:
                raise SystemExit("Autenticador inválido")
            user = User(
                id=uuid4(),
                login=args.login.lower(),
                password_hash=PASSWORDS.hash(password),
                mfa_secret=cipher(settings).encrypt(secret.encode()).decode(),
                active=True,
            )
            db.add(user)
            if args.command == "bootstrap-platform":
                db.add(PlatformOperator(user_id=user.id, active=True))
            elif args.command == "bootstrap":
                tenant = Tenant(id=uuid4(), name=args.tenant_name or "Administração da plataforma")
                db.add(tenant)
                db.flush()
                set_tenant(db, tenant.id)
                db.add(
                    Membership(
                        tenant_id=tenant.id,
                        user_id=user.id,
                        role="admin",
                        active=True,
                    )
                )
        else:
            if not user:
                raise SystemExit("Identidade não encontrada")
            raw = token()
            db.add(
                RecoveryToken(
                    token_hash=digest(settings, "recovery", raw),
                    user_id=user.id,
                    expires_at=datetime.now(UTC) + timedelta(minutes=15),
                )
            )
            # Explicit operator-only delivery, intentionally not stdout/logs.
            destination = getpass.getpass("Arquivo privado para token (fora do repositório): ")
            from pathlib import Path

            path = Path(destination).resolve()
            if path.is_relative_to(Path.cwd().resolve()):
                raise SystemExit("Use arquivo privado fora do repositório")
            with path.open("x", encoding="utf-8") as output:
                output.write(raw)
    engine.dispose()
    print("Operação concluída. Registre o procedimento no controle operacional.")


if __name__ == "__main__":
    main()
