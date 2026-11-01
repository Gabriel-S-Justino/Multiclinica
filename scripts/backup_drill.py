"""Exercise a real dump/restore on the disposable integration cluster only."""

import os
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import psycopg
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from backend.config import Settings
from backend.infrastructure.db import set_tenant
from backend.infrastructure.fields import seal, unseal
from backend.infrastructure.models import Tenant
from backend.infrastructure.scheduling_models import Contact


def main() -> None:
    if os.environ.get("APP_ENV") != "test":
        raise SystemExit("Restauração de ensaio restrita ao banco descartável de teste")
    settings = Settings()
    url = make_url(os.environ["TEST_ADMIN_URL"])
    if url.host != "127.0.0.1" or url.database != "clinic_test":
        raise SystemExit("Destino de teste inválido")
    started = time.monotonic()
    engine = create_engine(url, hide_parameters=True)
    tenant_id, contact_id = uuid4(), uuid4()
    value = "+15550009999"
    with Session(engine) as db, db.begin():
        expected_revision = db.scalar(text("SELECT version_num FROM alembic_version"))
        db.add(Tenant(id=tenant_id, name="Restore probe"))
        db.flush()
        db.add(
            Contact(
                id=contact_id,
                tenant_id=tenant_id,
                phone_hash=uuid4().hex * 2,
                phone_ciphertext=seal(settings, tenant_id, "contact", contact_id, "phone", value),
                active=True,
            )
        )
    env = os.environ.copy()
    env.update(
        PGHOST=url.host,
        PGPORT=str(url.port),
        PGUSER=str(url.username),
        PGPASSWORD=str(url.password),
    )
    suffix = ".exe" if os.name == "nt" else ""
    pg_bin = Path(env["PG_BIN"]).resolve()
    backup = Path(".local/restore-drill.dump").resolve()
    subprocess.run(
        [str(pg_bin / f"pg_dump{suffix}"), "-Fc", "--file", str(backup), "--dbname", "clinic_test"],
        env=env,
        check=True,
    )  # noqa: S603
    with psycopg.connect(
        host=url.host,
        port=url.port,
        user=url.username,
        password=url.password,
        dbname="postgres",
        autocommit=True,
    ) as conn:
        conn.execute("CREATE DATABASE clinic_restore")
    subprocess.run(
        [
            str(pg_bin / f"pg_restore{suffix}"),
            "--exit-on-error",
            "--dbname",
            "clinic_restore",
            str(backup),
        ],
        env=env,
        check=True,
    )  # noqa: S603
    restored = create_engine(url.set(database="clinic_restore"), hide_parameters=True)
    with Session(restored) as db:
        contact = db.get(Contact, contact_id)
        assert contact is not None
        assert (
            unseal(settings, tenant_id, "contact", contact_id, "phone", contact.phone_ciphertext)
            == value
        )
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == expected_revision
    runtime = create_engine(
        make_url(settings.database_url.get_secret_value()).set(database="clinic_restore"),
        hide_parameters=True,
    )
    with Session(runtime) as db, db.begin():
        assert not list(db.scalars(text("SELECT id FROM contacts")))
        set_tenant(db, tenant_id)
        assert db.scalar(text("SELECT id FROM contacts")) == contact_id
        assert not db.scalar(text("SELECT has_table_privilege(current_user,'audit_logs','UPDATE')"))
    for item in (runtime, restored, engine):
        item.dispose()
    print(
        f"Backup/restore PostgreSQL real: PASS; cifra, chave, schema, RLS e auditoria; {time.monotonic() - started:.2f}s; somente dados sintéticos"
    )


if __name__ == "__main__":
    main()
