from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.domain.permissions import ContactPrincipal, Principal, can_read_professional
from backend.infrastructure.models import Professional, ProfessionalAssignment


def visible_professionals(db: Session, identity: Principal) -> list[Professional]:
    statement = select(Professional).where(Professional.tenant_id == identity.tenant_id)
    if identity.role == "collaborator":
        statement = statement.where(Professional.user_id == identity.user_id)
    elif identity.role == "reception":
        assigned = select(ProfessionalAssignment.professional_id).where(
            ProfessionalAssignment.tenant_id == identity.tenant_id,
            ProfessionalAssignment.membership_id == identity.membership_id,
        )
        statement = statement.where(Professional.id.in_(assigned))
    elif identity.role != "admin" and not isinstance(identity, ContactPrincipal):
        return []
    return list(db.scalars(statement.order_by(Professional.id).limit(100)))


def read_professional(db: Session, identity: Principal, resource_id: UUID) -> Professional | None:
    resource = db.scalar(
        select(Professional).where(
            Professional.tenant_id == identity.tenant_id, Professional.id == resource_id
        )
    )
    if not resource:
        return None
    assigned = (
        db.get(ProfessionalAssignment, (identity.tenant_id, identity.membership_id, resource.id))
        is not None
    )
    return resource if can_read_professional(identity, resource.user_id, assigned) else None
