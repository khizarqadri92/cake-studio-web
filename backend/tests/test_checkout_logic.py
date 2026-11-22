from datetime import date, datetime, time, timedelta
from decimal import Decimal as D

import pytest

from app.services.coupons import CartLine, CouponError, CouponSpec, apply_coupon
from app.services.scheduling import ScheduleError, SlotSpec, available_slots, validate_choice
from app.services.totals import DeliveryRules, TaxRules, compute_totals

NOW = datetime(2026, 11, 17, 10, 0)
LINES = [CartLine(1, 10, D("60")), CartLine(2, 20, D("40"))]


def c(**kw):
    return CouponSpec(**{"code": "X", "kind": "percent", "value": D("10"), **kw})


def test_percent_fixed_and_caps():
    assert apply_coupon(c(), LINES, NOW, prior_orders=0) == D("10.00")
    assert apply_coupon(c(max_discount=D("4")), LINES, NOW, prior_orders=0) == D("4.00")
    assert apply_coupon(c(kind="fixed", value=D("25")), LINES, NOW, prior_orders=0) == D("25.00")
    assert apply_coupon(c(kind="fixed", value=D("500")), LINES, NOW, prior_orders=0) == D("100.00")  # capped at cart


def test_scoped_to_product_or_category():
    assert apply_coupon(c(product_ids=frozenset({1})), LINES, NOW, prior_orders=0) == D("6.00")
    assert apply_coupon(c(category_ids=frozenset({20})), LINES, NOW, prior_orders=0) == D("4.00")
    with pytest.raises(CouponError, match="does not apply"):
        apply_coupon(c(product_ids=frozenset({99})), LINES, NOW, prior_orders=0)


@pytest.mark.parametrize("kw,msg", [
    (dict(is_active=False), "not active"),
    (dict(starts_at=NOW + timedelta(days=1)), "not valid yet"),
    (dict(expires_at=NOW - timedelta(seconds=1)), "expired"),
    (dict(usage_limit=5, used_count=5), "usage limit"),
    (dict(min_order=D("100.01")), "Minimum"),
    (dict(per_customer_limit=1), "already used"),
])
def test_rejections(kw, msg):
    with pytest.raises(CouponError, match=msg):
        apply_coupon(c(**kw), LINES, NOW, prior_orders=0, customer_uses=1)


def test_first_order_only():
    spec = c(first_order_only=True)
    assert apply_coupon(spec, LINES, NOW, prior_orders=0) == D("10.00")
    for prior in (1, None):
        with pytest.raises(CouponError, match="first orders"):
            apply_coupon(spec, LINES, NOW, prior_orders=prior)


def test_totals_delivery_and_free_threshold():
    d = DeliveryRules(fee=D("5"), free_over=D("90"))
    t = compute_totals(D("100"), D("5"), "delivery", d, TaxRules())
    assert (t.delivery_fee, t.total) == (D("0.00"), D("95.00"))  # 95 >= 90 -> free
    t = compute_totals(D("100"), D("20"), "delivery", d, TaxRules())
    assert (t.delivery_fee, t.total) == (D("5.00"), D("85.00"))
    assert compute_totals(D("10"), D("0"), "pickup", d, TaxRules()).total == D("10.00")


def test_tax_inclusive_vs_exclusive():
    inc = compute_totals(D("110"), D("0"), "pickup", DeliveryRules(), TaxRules(True, D("10"), True))
    assert (inc.tax, inc.total) == (D("10.00"), D("110.00"))
    exc = compute_totals(D("100"), D("0"), "pickup", DeliveryRules(), TaxRules(True, D("10"), False))
    assert (exc.tax, exc.total) == (D("10.00"), D("110.00"))


def test_discount_cannot_exceed_subtotal():
    assert compute_totals(D("10"), D("50"), "pickup", DeliveryRules(), TaxRules()).total == D("0.00")


# Tue 2026-11-17 10:00. Slots every weekday.
ALL = frozenset(range(7))
SLOTS = [SlotSpec(1, time(9), time(12), 2, ALL), SlotSpec(2, time(14), time(17), 2, ALL),
         SlotSpec(3, time(17), time(20), 1, frozenset({5}))]


def test_prep_time_hides_early_slots():
    got = available_slots(date(2026, 11, 17), NOW, 24, SLOTS, set(), {})
    assert got == []  # ready tomorrow 10:00
    got = available_slots(date(2026, 11, 18), NOW, 24, SLOTS, set(), {})
    assert [s.slot_id for s in got] == [2]  # 09:00 slot starts before 10:00 ready time
    got = available_slots(date(2026, 11, 18), NOW, 2, SLOTS, set(), {})
    assert [s.slot_id for s in got] == [1, 2]


def test_blocked_full_past_inactive_weekday():
    day = date(2026, 11, 20)
    assert available_slots(day, NOW, 2, SLOTS, {day}, {}) == []
    full = available_slots(day, NOW, 2, SLOTS, set(), {1: 2})
    assert [s.slot_id for s in full] == [2]
    assert available_slots(date(2026, 11, 16), NOW, 0, SLOTS, set(), {}) == []
    assert 3 in [s.slot_id for s in available_slots(date(2026, 11, 21), NOW, 2, SLOTS, set(), {})]  # Saturday only
    assert 3 not in [s.slot_id for s in available_slots(date(2026, 11, 20), NOW, 2, SLOTS, set(), {})]
    off = [SlotSpec(1, time(9), time(12), 5, ALL, is_active=False)]
    assert available_slots(day, NOW, 2, off, set(), {}) == []


def test_validate_choice_and_min_prep():
    day = date(2026, 11, 19)
    kw = dict(day=day, now=NOW, prep_hours=2, slots=SLOTS, blocked=set(), booked={})
    assert validate_choice(2, **kw).slot_id == 2
    with pytest.raises(ScheduleError):
        validate_choice(1, **{**kw, "booked": {1: 2}})  # slot full
    with pytest.raises(ScheduleError):
        validate_choice(99, **kw)  # unknown slot
    assert available_slots(date(2026, 11, 17), NOW, 0, SLOTS, set(), {}, min_prep_hours=48) == []
