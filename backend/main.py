import hmac
import json
import logging
import time
from collections.abc import AsyncIterator, Generator
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import Engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.application import auth, portal
from backend.application.portal_access import PortalError
from backend.application.portal_session import capabilities
from backend.config import Settings
from backend.domain.scheduling import SchedulingError
from backend.infrastructure.db import make_engine, transaction
from backend.infrastructure.models import Membership, PortalSession, Tenant
from backend.infrastructure.portal_models import PlatformOperator
from backend.infrastructure.rate_limit import consume
from backend.infrastructure.security import digest
from backend.presentation.portal_routes import register_portal_routes
from backend.presentation.schemas import (
    Login,
    PasswordChange,
    RecoveryConfirm,
    RecoveryRequest,
    SelectMembership,
    VerifyMFA,
)
from backend.presentation.webhook_routes import register_webhooks

logger = logging.getLogger("clinic.requests")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
COOKIE = "__Host-clinic_session"
CSRF_COOKIE = "__Host-clinic_csrf"


def create_app(settings: Settings, engine: Engine | None = None) -> FastAPI:
    database = engine if engine is not None else make_engine(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        with transaction(database) as db:
            unsafe = db.scalar(
                text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname=current_user")
            )
            owner = db.scalar(
                text(
                    "SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tableowner=current_user"
                )
            )
            if unsafe or owner:
                raise RuntimeError("Use credenciais de runtime sem privilégios de migração")
            db.execute(text("SELECT 1 FROM professionals LIMIT 0"))
        yield
        database.dispose()

    app = FastAPI(
        title="Plataforma de Atendimento",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = database

    def db_session() -> Generator[Session, None, None]:
        with transaction(database) as db:
            yield db

    def current(
        request: Request, db: Session = Depends(db_session, scope="function")
    ) -> PortalSession:
        session = auth.get_session(db, settings, request.cookies.get(COOKIE))
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            supplied = request.headers.get("x-csrf-token", "")
            if request.headers.get("origin") != settings.public_origin or not hmac.compare_digest(
                digest(settings, "csrf", supplied), session.csrf_hash
            ):
                raise HTTPException(403, "csrf_failed")
        return session

    def cookies(response: Response, raw: str, csrf: str) -> None:
        response.set_cookie(COOKIE, raw, httponly=True, secure=True, samesite="lax", path="/")
        response.set_cookie(
            CSRF_COOKIE, csrf, httponly=False, secure=True, samesite="lax", path="/"
        )

    def login_origin(request: Request) -> None:
        if request.headers.get("origin") != settings.public_origin:
            raise HTTPException(403, "origin_denied")

    def throttle(request: Request, scope: str, subject: str = "") -> None:
        # Never trust forwarded IP headers from arbitrary clients.
        client_ip = request.client.host if request.client else "unknown"
        if not consume(database, settings, scope + ":ip", client_ip, 30):
            raise HTTPException(429, "rate_limited")
        if subject and not consume(database, settings, scope + ":subject", subject.lower(), 8):
            raise HTTPException(429, "rate_limited")

    @app.middleware("http")
    async def request_policy(request: Request, call_next: Any) -> Response:
        request.state.correlation_id = str(uuid4())
        started = time.perf_counter()
        length = request.headers.get("content-length", "0")
        try:
            oversized = int(length) > 65536 or int(length) < 0
        except ValueError:
            oversized = True
        if oversized:
            response: Response = JSONResponse(
                {
                    "error": {
                        "code": "payload_too_large",
                        "message": "Requisição inválida.",
                        "correlation_id": request.state.correlation_id,
                    }
                },
                status_code=413,
            )
        else:
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 65536:
                    break
            if len(body) > 65536:
                response = JSONResponse(
                    {
                        "error": {
                            "code": "payload_too_large",
                            "message": "Requisição inválida.",
                            "correlation_id": request.state.correlation_id,
                        }
                    },
                    status_code=413,
                )
            else:
                request._body = bytes(body)
                try:
                    response = await call_next(request)
                except Exception:
                    # Do not log exception strings: drivers/providers may include secrets.
                    response = JSONResponse(
                        {
                            "error": {
                                "code": "internal_error",
                                "message": "Não foi possível concluir a solicitação.",
                                "correlation_id": request.state.correlation_id,
                            }
                        },
                        status_code=500,
                    )
        response.headers.update(
            {
                "X-Correlation-ID": request.state.correlation_id,
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "Content-Security-Policy": (
                    "default-src 'none'; frame-ancestors 'none'"
                    if request.url.path == "/v1" or request.url.path.startswith("/v1/")
                    else (
                        "default-src 'self'; script-src 'self'; style-src 'self'; "
                        "connect-src 'self'; img-src 'self'; font-src 'self'; "
                        "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
                        "form-action 'self'"
                    )
                ),
                "Cache-Control": "no-store",
                "X-Frame-Options": "DENY",
            }
        )
        logger.info(
            json.dumps(
                {
                    "correlation_id": request.state.correlation_id,
                    "method": request.method,
                    "status": response.status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000),
                }
            )
        )
        return response

    def error_response(request: Request, status: int, code: str) -> JSONResponse:
        return JSONResponse(
            {
                "error": {
                    "code": code,
                    "message": "Não foi possível concluir a solicitação.",
                    "correlation_id": request.state.correlation_id,
                }
            },
            status_code=status,
        )

    @app.exception_handler(auth.AuthError)
    async def auth_error(request: Request, exc: auth.AuthError) -> JSONResponse:
        return error_response(request, 401, "authentication_failed")

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        return error_response(request, exc.status_code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return error_response(request, 422, "validation_failed")

    @app.exception_handler(ValidationError)
    async def command_validation_error(request: Request, exc: ValidationError) -> JSONResponse:
        return error_response(request, 422, "validation_failed")

    @app.exception_handler(PortalError)
    async def portal_error(request: Request, exc: PortalError) -> JSONResponse:
        return error_response(request, exc.status, exc.code)

    @app.exception_handler(IntegrityError)
    async def integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
        return error_response(request, 409, "data_conflict")

    @app.exception_handler(SchedulingError)
    async def scheduling_error(request: Request, exc: SchedulingError) -> JSONResponse:
        if exc.code == "permission_denied":
            status = 403
        elif exc.code in {
            "appointment_unavailable",
            "professional_unavailable",
            "unit_unavailable",
            "identity_unverified",
        }:
            status = 404
        elif exc.code in {
            "invalid_patient_data",
            "patient_data_required",
            "unnecessary_patient_data",
            "timezone_required",
            "invalid_interval",
            "invalid_policy",
        }:
            status = 422
        else:
            status = 409
        return error_response(request, status, exc.code)

    @app.get("/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/auth/login")
    def login(
        command: Login,
        request: Request,
        response: Response,
        db: Session = Depends(db_session, scope="function"),
    ) -> dict[str, str]:
        login_origin(request)
        throttle(request, "login", command.login)
        raw, csrf = auth.login(db, settings, command.login, command.password)
        if csrf is None:
            return {"status": "mfa_required", "challenge": raw}
        cookies(response, raw, csrf)
        return {"status": "authenticated"}

    @app.post("/v1/auth/mfa/verify")
    def mfa(
        command: VerifyMFA,
        request: Request,
        response: Response,
        db: Session = Depends(db_session, scope="function"),
    ) -> dict[str, str]:
        login_origin(request)
        throttle(request, "mfa", command.challenge)
        raw, csrf = auth.verify_mfa(db, settings, command.challenge, command.code)
        cookies(response, raw, csrf)
        return {"status": "authenticated"}

    @app.get("/v1/auth/session")
    def session_info(
        session: PortalSession = Depends(current),
        db: Session = Depends(db_session, scope="function"),
    ) -> dict[str, Any]:
        memberships = list(
            db.execute(
                select(Membership, Tenant)
                .join(Tenant, Tenant.id == Membership.tenant_id)
                .where(
                    Membership.user_id == session.user_id,
                    Membership.active.is_(True),
                    Tenant.active.is_(True),
                )
            )
        )
        operator = db.get(PlatformOperator, session.user_id)
        return {
            "user_id": str(session.user_id),
            "active_membership_id": str(session.membership_id) if session.membership_id else None,
            "memberships": [
                {
                    "id": str(item.id),
                    "tenant_id": str(item.tenant_id),
                    "role": item.role,
                    "clinic_name": tenant.name,
                    "timezone": tenant.timezone,
                    "capabilities": capabilities(
                        item, bool(operator and operator.active), session.mfa_verified
                    ),
                }
                for item, tenant in memberships
            ],
        }

    @app.post("/v1/auth/active-membership")
    def active_membership(
        command: SelectMembership,
        response: Response,
        session: PortalSession = Depends(current),
        db: Session = Depends(db_session, scope="function"),
    ) -> dict[str, str]:
        raw, csrf = auth.rotate_membership(db, settings, session, command.membership_id)
        cookies(response, raw, csrf)
        return {"status": "authenticated"}

    @app.post("/v1/auth/logout", status_code=204)
    def logout(
        response: Response,
        session: PortalSession = Depends(current),
        db: Session = Depends(db_session, scope="function"),
    ) -> None:
        db.delete(session)
        response.delete_cookie(COOKIE, secure=True, httponly=True, samesite="lax")
        response.delete_cookie(CSRF_COOKIE, secure=True, samesite="lax")

    @app.post("/v1/auth/password/change", status_code=204)
    def change_own_password(
        command: PasswordChange,
        request: Request,
        db: Session = Depends(db_session, scope="function"),
    ) -> None:
        login_origin(request)
        throttle(request, "password-change", command.login)
        auth.change_password(
            db,
            settings,
            command.login,
            command.current_password.get_secret_value(),
            command.new_password.get_secret_value(),
            command.code,
        )

    @app.post("/v1/auth/recovery/request", status_code=202)
    def recovery_request(command: RecoveryRequest, request: Request) -> dict[str, str]:
        login_origin(request)
        throttle(request, "recovery", command.login)
        # No verified mail delivery provider yet: do not mint or expose recovery tokens.
        # Operators can issue single-use tokens via the controlled CLI.
        return {
            "status": "received",
            "message": "Se necessário, procure o administrador para recuperar o acesso.",
        }

    @app.post("/v1/auth/recovery/confirm", status_code=204)
    def recovery_confirm(
        command: RecoveryConfirm,
        request: Request,
        db: Session = Depends(db_session, scope="function"),
    ) -> None:
        login_origin(request)
        throttle(request, "recovery-confirm", command.token)
        auth.complete_recovery(db, settings, command.token, command.password)

    @app.get("/v1/professionals")
    def professionals(
        session: PortalSession = Depends(current),
        db: Session = Depends(db_session, scope="function"),
    ) -> dict[str, Any]:
        identity = auth.principal(db, session)
        return {
            "items": [
                {"id": str(item.id), "display_name": item.display_name, "active": item.active}
                for item in portal.visible_professionals(db, identity)
            ]
        }

    @app.get("/v1/professionals/{resource_id}")
    def professional(
        resource_id: UUID,
        session: PortalSession = Depends(current),
        db: Session = Depends(db_session, scope="function"),
    ) -> dict[str, Any]:
        identity = auth.principal(db, session)
        item = portal.read_professional(db, identity, resource_id)
        if not item:
            raise HTTPException(404, "not_found")
        return {"id": str(item.id), "display_name": item.display_name, "active": item.active}

    # Fail startup/readiness on privileged runtime credentials, including table owner bypass.
    @app.get("/v1/ready")
    def ready(db: Session = Depends(db_session, scope="function")) -> dict[str, str]:
        unsafe = db.scalar(
            text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname=current_user")
        )
        owner = db.scalar(
            text(
                "SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tableowner=current_user"
            )
        )
        if unsafe or owner:
            raise HTTPException(503, "unavailable")
        return {"status": "ok"}

    register_portal_routes(app, settings, db_session, current)
    register_webhooks(app, settings, db_session)
    # Publish the built Vite frontend without changing the existing API routes.
    app.frontend("/", directory="public", fallback="index.html", check_dir=False)
    return app
