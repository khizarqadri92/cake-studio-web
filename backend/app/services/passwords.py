"""Customer password policy and one-time token helpers (pure)."""
import hashlib
import secrets
from datetime import datetime

COMMON = {"password", "password1", "12345678", "123456789", "1234567890", "qwertyuiop", "iloveyou1", "letmein123", "welcome123", "cakestudio"}


class PasswordError(ValueError):
    pass


def validate_password(pw: str, email: str = "") -> None:
    if len(pw) < 10:
        raise PasswordError("Password must be at least 10 characters")
    if len(pw) > 128:
        raise PasswordError("Password must be at most 128 characters")
    low = pw.lower()
    if low in COMMON or (email and low == email.lower()) or len(set(low)) < 4:
        raise PasswordError("Please choose a less guessable password")


def new_token() -> tuple[str, str]:
    """(raw, sha256). Only the hash is stored; the raw value goes in the emailed link."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def token_usable(expires_at: datetime, used_at: datetime | None, now: datetime) -> bool:
    return used_at is None and now < expires_at
