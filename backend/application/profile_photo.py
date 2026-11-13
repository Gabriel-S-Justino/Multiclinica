import base64
import binascii

from backend.application.portal_access import PortalError


def decode_profile_photo(jpeg: str | None) -> bytes | None:
    if jpeg is None:
        return None
    try:
        photo = base64.b64decode(jpeg, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise PortalError("invalid_photo", 422) from exc
    if not photo.startswith(b"\xff\xd8\xff") or not photo.endswith(b"\xff\xd9"):
        raise PortalError("invalid_photo", 422)
    return photo
