from backend.infrastructure.models import Membership


def capabilities(member: Membership, platform_operator: bool, mfa_verified: bool) -> list[str]:
    if member.role == "superadmin":
        return ["platform.manage"] if platform_operator and mfa_verified else []
    result = ["agenda.read", "appointments.write"]
    if member.role == "admin" or member.can_manage_schedule:
        result.append("schedules.manage")
    if member.role in {"admin", "reception"}:
        result.extend(["inbox.read", "identity.verify"])
    if member.role == "admin":
        result.extend(["services.manage", "team.manage", "settings.manage", "support.review"])
        if mfa_verified:
            result.extend(["audit.read", "integrations.manage"])
    return result
