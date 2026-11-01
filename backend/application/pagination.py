import base64
import hmac
import json
from datetime import timedelta
from typing import Any

from backend.application.portal_access import PortalContext, PortalError, now
from backend.infrastructure.security import digest


def filter_key(filters: dict[str, Any]) -> str:
    return json.dumps(filters, sort_keys=True, separators=(",", ":"), default=str)


def offset_for(ctx: PortalContext, cursor: str | None, scope: str, filters: dict[str, Any]) -> int:
    if not cursor:
        return 0
    if len(cursor) > 2048:
        raise PortalError("invalid_cursor", 422)
    try:
        payload, signature = cursor.rsplit(".", 1)
        if not hmac.compare_digest(signature, digest(ctx.settings, "cursor", payload)):
            raise ValueError
        value = json.loads(base64.urlsafe_b64decode(payload.encode()))
        expected = [
            str(ctx.tenant_id),
            str(ctx.identity.user_id),
            str(ctx.identity.membership_id),
            scope,
            filter_key(filters),
        ]
        if value["scope"] != expected or value["expires"] <= now(ctx.db).timestamp():
            raise ValueError
        offset = value["offset"]
        if not isinstance(offset, int) or isinstance(offset, bool) or not 0 <= offset <= 100000:
            raise ValueError
        return offset
    except (ValueError, TypeError, KeyError, UnicodeError) as error:
        raise PortalError("invalid_cursor", 422) from error


def cursor_for(
    ctx: PortalContext, offset: int | None, scope: str, filters: dict[str, Any]
) -> str | None:
    if offset is None:
        return None
    value = {
        "offset": offset,
        "expires": int((now(ctx.db) + timedelta(minutes=15)).timestamp()),
        "scope": [
            str(ctx.tenant_id),
            str(ctx.identity.user_id),
            str(ctx.identity.membership_id),
            scope,
            filter_key(filters),
        ],
    }
    payload = base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).decode()
    return payload + "." + digest(ctx.settings, "cursor", payload)
