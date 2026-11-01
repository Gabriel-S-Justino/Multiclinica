from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    tenant_id: UUID
    membership_id: UUID
    role: str
    mfa_verified: bool
    authenticated_at: datetime | None = None
    can_manage_schedule: bool = False


@dataclass(frozen=True)
class ContactPrincipal(Principal):
    """Internal worker identity; never constructed from request fields or portal sessions."""

    channel_id: UUID | None = None
    contact_id: UUID | None = None


def can_read_professional(principal: Principal, user_id: UUID | None, assigned: bool) -> bool:
    if isinstance(principal, ContactPrincipal):
        return principal.role == "messaging"
    if principal.role == "admin":
        return True
    if principal.role == "collaborator":
        return user_id == principal.user_id
    return principal.role == "reception" and assigned


def can_read_audit(principal: Principal) -> bool:
    return principal.role == "admin" and principal.mfa_verified
