"""Custom cake quotation lifecycle (pure)."""
from datetime import date
from decimal import Decimal
import re

STATUSES = ("new", "quoted", "approved", "declined", "expired", "converted")
_NEXT = {
    "new": {"quoted", "declined"},
    "quoted": {"quoted", "approved", "declined", "expired"},  # quoted -> quoted = revised quote
    "approved": {"converted", "declined"},
    "declined": set(), "expired": set(), "converted": set(),
}
IMAGE_URL = re.compile(r"^/media/[0-9a-f]{32}\.(png|jpg|webp|gif)$")  # only files our own upload endpoint produced


class CakeFlowError(ValueError):
    pass


def check_transition(old: str, new: str) -> None:
    if new not in _NEXT.get(old, set()):
        raise CakeFlowError(f"A request that is '{old}' cannot become '{new}'")


def validate_required_date(required: date, today: date, min_days: int, max_days_ahead: int = 365) -> None:
    if (required - today).days < min_days:
        raise CakeFlowError(f"Custom cakes need at least {min_days} day{'s' if min_days != 1 else ''} notice")
    if (required - today).days > max_days_ahead:
        raise CakeFlowError("That date is too far in the future")


def validate_quote(price: Decimal, valid_until: date | None, today: date, required: date) -> None:
    if price <= 0:
        raise CakeFlowError("Quoted price must be greater than zero")
    if valid_until is not None:
        if valid_until < today:
            raise CakeFlowError("Quote validity date is in the past")


def is_quote_expired(valid_until: date | None, today: date) -> bool:
    return valid_until is not None and today > valid_until


def _own_url(u: str, public_base: str | None) -> bool:
    if IMAGE_URL.match(u):
        return True
    if public_base:  # S3 mode: only files our upload code produced (random name under uploads/) on our configured host
        return re.fullmatch(re.escape(public_base.rstrip("/")) + r"/uploads/[0-9a-f]{32}\.(png|jpg|webp|gif)", u) is not None
    return False


def validate_images(urls: list[str], limit: int = 3, public_base: str | None = None) -> list[str]:
    if len(urls) > limit:
        raise CakeFlowError(f"At most {limit} reference images")
    if len(set(urls)) != len(urls) or any(not _own_url(u, public_base) for u in urls):
        raise CakeFlowError("Invalid reference image")
    return urls
