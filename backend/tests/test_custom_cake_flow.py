from datetime import date
from decimal import Decimal as D

import pytest

from app.services.custom_cake_flow import (CakeFlowError, check_transition, is_quote_expired, validate_images,
                                           validate_quote, validate_required_date)

T = date(2026, 11, 18)


def test_transitions():
    for a, b in [("new", "quoted"), ("quoted", "quoted"), ("quoted", "approved"), ("approved", "converted"), ("quoted", "expired")]:
        check_transition(a, b)
    for a, b in [("new", "approved"), ("new", "converted"), ("quoted", "converted"), ("converted", "declined"), ("declined", "quoted"), ("expired", "approved")]:
        with pytest.raises(CakeFlowError):
            check_transition(a, b)


def test_required_date_window():
    validate_required_date(date(2026, 11, 21), T, 3)
    with pytest.raises(CakeFlowError, match="at least 3 days"):
        validate_required_date(date(2026, 11, 20), T, 3)
    with pytest.raises(CakeFlowError, match="too far"):
        validate_required_date(date(2028, 1, 1), T, 3)


def test_quote_validation_and_expiry():
    validate_quote(D("120"), date(2026, 11, 25), T, date(2026, 12, 1))
    for price, vu in [(D("0"), None), (D("-1"), None), (D("10"), date(2026, 11, 1))]:
        with pytest.raises(CakeFlowError):
            validate_quote(price, vu, T, date(2026, 12, 1))
    assert not is_quote_expired(date(2026, 11, 18), T) and is_quote_expired(date(2026, 11, 17), T) and not is_quote_expired(None, T)


def test_reference_images_must_be_our_uploads():
    ok = "/media/" + "a" * 32 + ".png"
    assert validate_images([ok]) == [ok]
    for bad in (["https://evil.com/x.png"], ["/media/../etc/passwd"], ["/media/" + "a" * 32 + ".svg"], [ok, ok], [ok.replace("a", "b", 1)] * 4):
        with pytest.raises(CakeFlowError):
            validate_images(bad)


def test_s3_reference_images_only_from_our_host_and_naming():
    base = "https://cdn.example.com"
    ok = f"{base}/uploads/{'a' * 32}.png"
    assert validate_images([ok], public_base=base) == [ok]
    for bad in (f"https://evil.example.com/uploads/{'a' * 32}.png", f"{base}/uploads/../x.png", f"{base}.evil.com/uploads/{'a' * 32}.png", f"{base}/other/{'a' * 32}.png"):
        with pytest.raises(CakeFlowError):
            validate_images([bad], public_base=base)
    with pytest.raises(CakeFlowError):  # without S3 configured, remote URLs are never accepted
        validate_images([ok])
