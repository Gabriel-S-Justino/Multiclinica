"""Start a disposable PostgreSQL cluster, test migrations and run the whole suite.

Requires PG_BIN pointing at installed PostgreSQL binaries. No system service is created.
All data stays in an ignored .local directory; a fresh cluster is used on every run.
"""

import os
import secrets
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

import psycopg
from cryptography.fernet import Fernet
from psycopg import sql


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    pg_bin = Path(os.environ["PG_BIN"]).resolve()
    suffix = ".exe" if os.name == "nt" else ""
    local = root / ".local"
    local.mkdir(exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="pg-test-", dir=local))
    password = secrets.token_hex(24)
    pwfile = directory / "password"
    pwfile.write_text(password, encoding="ascii")
    cluster = directory / "data"
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    env = dict(os.environ)
    env.update(
        {
            "APP_ENV": "test",
            "PUBLIC_ORIGIN": "https://testserver",
            "TOKEN_KEY": secrets.token_hex(32),
            "FIELD_KEY": Fernet.generate_key().decode(),
            "MFA_REQUIRED": "false",
            "PGOPTIONS": "-c statement_timeout=20000 -c lock_timeout=10000",
        }
    )
    base = f"127.0.0.1:{port}/clinic_test"
    env["DATABASE_URL"] = f"postgresql+psycopg://clinic_runtime:{password}@{base}"
    env["MIGRATION_DATABASE_URL"] = f"postgresql+psycopg://clinic_migrator:{password}@{base}"
    env["TEST_ADMIN_URL"] = f"postgresql+psycopg://postgres:{password}@{base}"

    def run(args: list[str]) -> None:
        subprocess.run(args, check=True, cwd=root, env=env)  # noqa: S603

    run(
        [
            str(pg_bin / f"initdb{suffix}"),
            "-D",
            str(cluster),
            "-U",
            "postgres",
            "--auth=scram-sha-256",
            "--pwfile",
            str(pwfile),
            "--encoding=UTF8",
            "--locale=C",
        ]
    )
    pwfile.unlink()
    started = False
    try:
        run(
            [
                str(pg_bin / f"pg_ctl{suffix}"),
                "-D",
                str(cluster),
                "-l",
                str(directory / "server.log"),
                "-o",
                f"-h 127.0.0.1 -p {port}",
                "-w",
                "start",
            ]
        )
        started = True
        with psycopg.connect(
            host="127.0.0.1",
            port=port,
            dbname="postgres",
            user="postgres",
            password=password,
            autocommit=True,
        ) as conn:
            for role in ("clinic_migrator", "clinic_runtime"):
                conn.execute(
                    sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOBYPASSRLS").format(
                        sql.Identifier(role), sql.Literal(password)
                    )
                )
            conn.execute("CREATE DATABASE clinic_test OWNER clinic_migrator")
            print("PostgreSQL real:", conn.execute("SELECT version()").fetchone()[0], flush=True)
        run([sys.executable, "-m", "alembic", "upgrade", "0001"])
        # Upgrade over existing data is exercised before pytest, without resetting schema.
        with psycopg.connect(
            host="127.0.0.1",
            port=port,
            dbname="clinic_test",
            user="postgres",
            password=password,
            autocommit=True,
        ) as conn:
            conn.execute(
                "INSERT INTO tenants(id,name,timezone,active) VALUES ('00000000-0000-0000-0000-000000000001','Migration probe','America/Sao_Paulo',true)"
            )
        run([sys.executable, "-m", "alembic", "upgrade", "head"])
        with psycopg.connect(
            host="127.0.0.1",
            port=port,
            dbname="clinic_test",
            user="postgres",
            password=password,
            autocommit=True,
        ) as conn:
            assert conn.execute("SELECT count(*) FROM tenants").fetchone()[0] == 1
        if os.environ.get("E2E_ONLY") != "1":
            run([sys.executable, "-m", "pytest", "--junitxml=.local/pytest.xml"])
        if os.environ.get("RUN_E2E") == "1":
            env["E2E_PASSWORD"] = secrets.token_urlsafe(24)
            run([sys.executable, "-m", "tests.seed_browser"])
            run(
                ["npm.cmd" if os.name == "nt" else "npm", "--prefix", "frontend", "run", "test:e2e"]
            )
        if os.environ.get("BACKUP_DRILL") == "1":
            run([sys.executable, "-m", "scripts.backup_drill"])
        run([sys.executable, "-m", "alembic", "downgrade", "base"])
        run([sys.executable, "-m", "alembic", "upgrade", "head"])
        print("Migration upgrade / existing data / downgrade / upgrade: PASS", flush=True)
        return 0
    finally:
        if started:
            run([str(pg_bin / f"pg_ctl{suffix}"), "-D", str(cluster), "-m", "fast", "-w", "stop"])


if __name__ == "__main__":
    raise SystemExit(main())
