import os

import jwt
import pytest

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET", "test-secret-test-secret-test-secret!")

from app.core import security  # noqa: E402


def test_password_hash_roundtrip():
    h = security.hash_password("s3cret-pass")
    assert h != "s3cret-pass"
    assert security.verify_password("s3cret-pass", h)
    assert not security.verify_password("wrong", h)


def test_access_token_roundtrip_and_type():
    tok = security.create_access_token("42")
    payload = security.decode_access_token(tok)
    assert payload["sub"] == "42" and payload["principal"] == "staff"


def test_tampered_token_rejected():
    tok = security.create_access_token("42")
    with pytest.raises(jwt.PyJWTError):
        security.decode_access_token(tok[:-2] + "xx")


def test_refresh_tokens_are_hashed_and_unique():
    a_raw, a_hash = security.new_refresh_token()
    b_raw, _ = security.new_refresh_token()
    assert a_raw != b_raw and a_raw != a_hash
    assert security.hash_refresh_token(a_raw) == a_hash
