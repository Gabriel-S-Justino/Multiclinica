"""Controlled channel provisioning and bounded worker invocations. No daemon in HTTP."""

import argparse
import os
import re
from uuid import UUID, uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.application.messaging_worker import process_one, send_one
from backend.config import Settings
from backend.infrastructure.db import make_engine, set_tenant
from backend.infrastructure.messaging_models import MessagingChannel
from backend.infrastructure.models import Membership, Tenant, User
from backend.infrastructure.portal_models import ServiceQueue
from backend.infrastructure.security import PASSWORDS, token


def main() -> None:
    parser = argparse.ArgumentParser(description="Canal WhatsApp e worker transacional")
    parser.add_argument("command", choices=["provision", "process", "send"])
    parser.add_argument("--channel-id", type=UUID)
    parser.add_argument("--tenant-id", type=UUID)
    parser.add_argument("--queue-id", type=UUID)
    parser.add_argument("--phone-number-id")
    parser.add_argument("--account-id")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    settings = Settings()
    if not 1 <= args.limit <= 1000:
        raise SystemExit("Limite inválido")
    if args.command == "provision":
        url = os.environ.get("MIGRATION_DATABASE_URL")
        if (
            not url
            or not args.tenant_id
            or not args.queue_id
            or not re.fullmatch(r"[0-9]{1,80}", args.phone_number_id or "")
            or not re.fullmatch(r"[0-9]{1,80}", args.account_id or "")
        ):
            raise SystemExit("Informe clínica, fila, número, conta e credenciais de migração")
        engine = create_engine(url, hide_parameters=True)
        with Session(engine) as db, db.begin():
            set_tenant(db, args.tenant_id)
            queue, tenant = db.get(ServiceQueue, args.queue_id), db.get(Tenant, args.tenant_id)
            if (
                not tenant
                or not tenant.active
                or not queue
                or queue.tenant_id != tenant.id
                or not queue.active
            ):
                raise SystemExit("Clínica/fila inválidas")
            if db.scalar(
                select(MessagingChannel.id).where(MessagingChannel.tenant_id == tenant.id)
            ):
                raise SystemExit(
                    "Canal já provisionado; alterar somente por procedimento de rotação"
                )
            user_id, member_id, channel_id = uuid4(), uuid4(), uuid4()
            db.add(
                User(
                    id=user_id,
                    login=f"service-{channel_id}@internal.invalid",
                    password_hash=PASSWORDS.hash(token()),
                    active=True,
                    is_service=True,
                )
            )
            db.flush()
            db.add(
                Membership(
                    id=member_id,
                    tenant_id=tenant.id,
                    user_id=user_id,
                    role="messaging",
                    active=True,
                )
            )
            db.flush()
            db.add(
                MessagingChannel(
                    id=channel_id,
                    tenant_id=tenant.id,
                    phone_number_id=args.phone_number_id,
                    account_id=args.account_id,
                    actor_user_id=user_id,
                    actor_membership_id=member_id,
                    default_queue_id=queue.id,
                    active=True,
                    send_enabled=False,
                )
            )
            print(f"Canal provisionado: {channel_id}; envio desativado")
    else:
        if not args.channel_id:
            raise SystemExit("Informe --channel-id")
        engine = make_engine(settings)
        operation = process_one if args.command == "process" else send_one
        completed = 0
        for _ in range(args.limit):
            if not operation(engine, settings, args.channel_id):
                break
            completed += 1
        print(f"Itens processados: {completed}")
    engine.dispose()


if __name__ == "__main__":
    main()
