"""Regression tests for the public portal security headers."""

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine

from backend.config import Settings
from backend.main import create_app


def test_frontend_csp_allows_local_assets_and_api_remains_restricted(tmp_path, monkeypatch):
    public = tmp_path / "public"
    assets = public / "assets"
    assets.mkdir(parents=True)
    (public / "index.html").write_text(
        '<!doctype html><div id="root"></div><script type="module" src="/assets/app.js"></script>',
        encoding="utf-8",
    )
    (assets / "app.js").write_text(
        'document.getElementById("root").textContent="loaded";', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    settings = Settings(
        app_env="test",
        database_url=SecretStr("postgresql+psycopg://clinic_runtime:unused@localhost/neondb"),
        public_origin="https://multclinicai.vercel.app",
        token_key=SecretStr("0123456789ABCDEF" * 4),
        field_key=SecretStr(Fernet.generate_key().decode()),
    )
    app = create_app(settings, engine=create_engine("sqlite+pysqlite:///:memory:"))
    client = TestClient(app)  # No lifespan: these routes do not access the database.

    page = client.get("/")
    script = client.get("/assets/app.js")
    api = client.get("/v1/health")

    assert page.status_code == 200
    assert script.status_code == 200
    assert api.status_code == 200
    for response in (page, script):
        csp = response.headers["content-security-policy"]
        assert "default-src 'self'" in csp
        assert "script-src 'self'" in csp
        assert "style-src 'self'" in csp
        assert "object-src 'none'" in csp
    assert api.headers["content-security-policy"] == ("default-src 'none'; frame-ancestors 'none'")
