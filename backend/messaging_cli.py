"""Processador de mensagens do WhatsApp (worker sempre ligado) e operações controladas.

O processamento não roda nas funções HTTP da Vercel: este módulo é o processo contínuo
hospedado à parte (ver Dockerfile.worker e docs/worker-deployment.md).
"""

import argparse
import logging
import os
import re
import signal
import time
from uuid import UUID

from sqlalchemy import Engine, create_engine, func, select, text
from sqlalchemy.orm import Session

from backend.application.maintenance import heartbeat, purge_expired
from backend.application.messaging_worker import process_one, send_one
from backend.application.webhooks import credentials
from backend.config import Settings
from backend.infrastructure.db import make_engine, set_tenant, transaction
from backend.infrastructure.messaging_models import (
    Dispatch,
    InboundJob,
    MessagingChannel,
    MessagingSession,
)
from backend.infrastructure.models import Tenant
from backend.infrastructure.portal_models import ServiceQueue


def active_channels(engine: Engine) -> list[UUID]:
    with transaction(engine) as db:
        return list(
            db.scalars(
                select(MessagingChannel.id)
                .join(Tenant, Tenant.id == MessagingChannel.tenant_id)
                .where(MessagingChannel.active.is_(True), Tenant.active.is_(True))
                .order_by(MessagingChannel.id)
            )
        )


MAINTENANCE_INTERVAL_SECONDS = 600


def run_worker(engine: Engine, settings: Settings, limit: int, interval: int) -> None:
    logger = logging.getLogger("clinic.messaging")
    last_maintenance = 0.0
    stopping = False

    def stop(_signum: int, _frame: object) -> None:
        # A hospedagem envia SIGTERM ao reiniciar: termina o ciclo atual e sai sem
        # interromper uma transação no meio.
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    logger.info("Processador de mensagens iniciado")
    while not stopping:
        try:
            heartbeat(engine)
            if time.monotonic() - last_maintenance >= MAINTENANCE_INTERVAL_SECONDS:
                removed = purge_expired(engine)
                last_maintenance = time.monotonic()
                logger.info("Limpeza de credenciais vencidas: %s", removed)
        except Exception:
            logger.error("Falha na manutenção periódica")
        try:
            channels = active_channels(engine)
        except Exception:
            logger.error("Falha ao consultar canais")
            time.sleep(interval)
            continue
        for channel_id in channels:
            if stopping:
                break
            for operation in (process_one, send_one):
                try:
                    for _ in range(limit):
                        if not operation(engine, settings, channel_id):
                            break
                except Exception:
                    logger.error("Falha no executor %s, canal %s", operation.__name__, channel_id)
        for _ in range(interval):
            if stopping:
                break
            time.sleep(1)
    logger.info("Processador de mensagens encerrado")


def set_delivery(db: Session, settings: Settings, channel_id: UUID, enabled: bool) -> None:
    channel = db.get(MessagingChannel, channel_id)
    if not channel:
        raise SystemExit("Canal inexistente")
    set_tenant(db, channel.tenant_id)
    db.execute(text("SELECT public.lock_schedule(:tenant)"), {"tenant": channel.tenant_id})
    db.refresh(channel)
    if enabled:
        tenant = db.get(Tenant, channel.tenant_id)
        queue = db.get(ServiceQueue, channel.default_queue_id)
        values = credentials(db, settings, channel)
        if (
            not channel.active
            or not tenant
            or not tenant.active
            or not queue
            or not queue.active
            or not all(values.get(name) for name in ("access_token", "app_secret", "verify_token"))
            or values.get("phone_number_id") != channel.phone_number_id
            or values.get("account_id") != channel.account_id
            or values.get("queue_id") != str(queue.id)
            or not re.fullmatch(r"v[0-9]{1,3}\.0", values.get("graph_version", ""))
        ):
            raise SystemExit("Configuração do canal incompleta ou divergente")
        channel.graph_version = values["graph_version"]
    channel.send_enabled = enabled


def print_status(engine: Engine) -> None:
    for channel_id in active_channels(engine):
        with transaction(engine) as db:
            channel = db.get(MessagingChannel, channel_id)
            if channel is None:
                continue
            set_tenant(db, channel.tenant_id)
            inbound = dict(
                db.execute(
                    select(InboundJob.status, func.count())
                    .where(InboundJob.channel_id == channel_id)
                    .group_by(InboundJob.status)
                )
                .tuples()
                .all()
            )
            outbound = dict(
                db.execute(
                    select(Dispatch.status, func.count())
                    .join(MessagingSession, MessagingSession.id == Dispatch.session_id)
                    .where(MessagingSession.channel_id == channel_id)
                    .group_by(Dispatch.status)
                )
                .tuples()
                .all()
            )
            print(f"{channel_id} envio={channel.send_enabled} entrada={inbound} saída={outbound}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Canal WhatsApp e worker transacional")
    parser.add_argument(
        "command", choices=["process", "send", "worker", "enable", "disable", "status"]
    )
    parser.add_argument("--channel-id", type=UUID)
    parser.add_argument("--tenant-id", type=UUID)
    parser.add_argument("--queue-id", type=UUID)
    parser.add_argument("--phone-number-id")
    parser.add_argument("--account-id")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--interval", type=int, default=5)
    args = parser.parse_args()
    settings = Settings()
    if not 1 <= args.limit <= 1000 or not 1 <= args.interval <= 300:
        raise SystemExit("Limite inválido")
    if args.command == "status":
        engine = make_engine(settings)
        try:
            print_status(engine)
        finally:
            engine.dispose()
        return
    if args.command == "worker":
        logging.basicConfig(level=logging.INFO)
        engine = make_engine(settings)
        try:
            run_worker(engine, settings, args.limit, args.interval)
        except KeyboardInterrupt:
            return
        finally:
            engine.dispose()
        return
    if args.command in {"enable", "disable"}:
        url = os.environ.get("MIGRATION_DATABASE_URL")
        if not url or not args.channel_id:
            raise SystemExit("Informe --channel-id e MIGRATION_DATABASE_URL")
        engine = create_engine(url, hide_parameters=True)
        try:
            with transaction(engine) as db:
                set_delivery(db, settings, args.channel_id, args.command == "enable")
        finally:
            engine.dispose()
        print("Estado de envio atualizado")
        return
    if args.command in {"process", "send"}:
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
