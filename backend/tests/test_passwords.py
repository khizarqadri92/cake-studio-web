from datetime import datetime, timedelta, timezone

import pytest

from app.services.passwords import PasswordError, hash_token, new_token, token_usable, validate_password


def test_policy():
    validate_password("correct horse battery")
    for bad in ["short1", "password", "aaaaaaaaaaaa", "a@b.com1234", "x" * 129]:
        with pytest.raises(PasswordError):
            validate_password(bad, "a@b.com1234")
    with pytest.raises(PasswordError):
        validate_password("Jane@Example.com", "jane@example.com")  # password equals the email


def test_tokens():
    raw, h = new_token()
    assert hash_token(raw) == h and raw != h and new_token()[0] != raw
    now = datetime(2026, 11, 18, tzinfo=timezone.utc)
    assert token_usable(now + timedelta(hours=1), None, now)
    assert not token_usable(now - timedelta(seconds=1), None, now)
    assert not token_usable(now + timedelta(hours=1), now, now)
