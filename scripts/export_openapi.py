"""Export the API schema without database connection or configured credentials."""

import json
import secrets
from pathlib import Path

from cryptography.fernet import Fernet

from backend.config import Settings
from backend.main import create_app

settings = Settings(
    _env_file=None,
    app_env="test",
    database_url="postgresql+psycopg://localhost/schema_only",
    public_origin="https://schema.invalid",
    token_key=secrets.token_hex(32),
    field_key=Fernet.generate_key().decode(),
    mfa_required=False,
)
app = create_app(settings)
destination = Path(__file__).resolve().parents[1] / "docs/api/openapi.json"
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(
    json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
app.state.engine.dispose()
print("Contrato OpenAPI exportado; sem conexão com banco")
