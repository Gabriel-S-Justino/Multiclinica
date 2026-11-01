"""Synthetic browser fixture for the disposable database only."""

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.infrastructure.models import Membership, Professional, Tenant, Unit, User
from backend.infrastructure.scheduling_models import (
    ProfessionalSchedule,
    ProfessionalService,
    Service,
)
from backend.infrastructure.security import PASSWORDS

if os.environ.get("APP_ENV") != "test":
    raise RuntimeError("Fixture restrita ao ambiente de teste")
engine = create_engine(os.environ["TEST_ADMIN_URL"], hide_parameters=True)
with Session(engine) as db, db.begin():
    tenant_id, user_id = uuid4(), uuid4()
    db.add(Tenant(id=tenant_id, name="Clínica sintética E2E"))
    db.add(
        User(
            id=user_id,
            login="e2e@test.invalid",
            password_hash=PASSWORDS.hash(os.environ["E2E_PASSWORD"]),
            active=True,
        )
    )
    db.flush()
    db.add(Membership(tenant_id=tenant_id, user_id=user_id, role="collaborator", active=True))
    db.add(
        Professional(tenant_id=tenant_id, user_id=user_id, display_name="Profissional de teste E2E")
    )
    db.flush()
    professional = db.query(Professional).filter_by(tenant_id=tenant_id).one()
    unit = Unit(tenant_id=tenant_id, name="Unidade E2E")
    service = Service(
        tenant_id=tenant_id,
        name="Consulta E2E",
        policy_validated=True,
        duration_minutes=30,
        step_minutes=30,
        buffer_before=0,
        buffer_after=0,
        min_notice_minutes=0,
        cancellation_notice_minutes=0,
        reschedule_notice_minutes=0,
        horizon_days=7,
        max_reschedules=2,
        hold_ttl_minutes=10,
    )
    db.add_all([unit, service])
    db.flush()
    db.add(
        ProfessionalService(
            tenant_id=tenant_id, professional_id=professional.id, service_id=service.id
        )
    )
    for weekday in range(7):
        db.add(
            ProfessionalSchedule(
                tenant_id=tenant_id,
                professional_id=professional.id,
                unit_id=unit.id,
                weekday=weekday,
                start_minute=480,
                end_minute=1080,
                valid_from=(datetime.now(UTC) - timedelta(days=1)).date(),
            )
        )
engine.dispose()
