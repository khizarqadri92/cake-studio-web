from decimal import Decimal as D

import pytest

from app.services.messages import OrderView, render
from app.services.order_flow import FlowError, allowed_next, check_refund, check_transition, net_paid, payment_status
from app.services.ratelimit import RateLimiter


def test_happy_paths_delivery_and_pickup():
    for path, f in ((["confirmed", "in_preparation", "out_for_delivery", "delivered"], "delivery"),
                    (["confirmed", "in_preparation", "ready_for_pickup", "delivered"], "pickup")):
        cur = "pending_confirmation"
        for nxt in path:
            check_transition(cur, nxt, f)
            cur = nxt


def test_fulfillment_specific_steps_blocked():
    with pytest.raises(FlowError):
        check_transition("in_preparation", "out_for_delivery", "pickup")
    with pytest.raises(FlowError):
        check_transition("in_preparation", "ready_for_pickup", "delivery")


@pytest.mark.parametrize("a,b", [("pending_confirmation", "delivered"), ("delivered", "cancelled"),
                                 ("cancelled", "confirmed"), ("refunded", "delivered"), ("confirmed", "bogus")])
def test_illegal_transitions(a, b):
    with pytest.raises(FlowError):
        check_transition(a, b, "delivery")


def test_terminal_states():
    assert allowed_next("refunded", "delivery") == set()
    assert allowed_next("delivered", "pickup") == {"refunded"}


def test_payment_status_and_net():
    t = D("100")
    assert payment_status(t, [(D("100"), "pending")]) == "unpaid"  # unverified money does not count
    assert payment_status(t, [(D("40"), "verified")]) == "partially_paid"
    assert payment_status(t, [(D("40"), "verified"), (D("60"), "verified")]) == "paid"
    assert payment_status(t, [(D("100"), "verified"), (D("-100"), "verified")]) == "refunded"
    assert payment_status(t, [(D("100"), "verified"), (D("-30"), "verified")]) == "partially_paid"
    assert payment_status(t, [(D("100"), "failed")]) == "unpaid"
    assert net_paid([(D("50"), "verified"), (D("-20"), "verified"), (D("9"), "pending")]) == D("30")


def test_refund_limits():
    pays = [(D("100"), "verified"), (D("-30"), "verified")]
    check_refund(D("70"), pays)
    with pytest.raises(FlowError):
        check_refund(D("70.01"), pays)
    with pytest.raises(FlowError):
        check_refund(D("0"), pays)
    with pytest.raises(FlowError):
        check_refund(D("1"), [(D("100"), "pending")])


def test_rate_limiter_window():
    t = [0.0]
    rl = RateLimiter(clock=lambda: t[0])
    assert all(rl.allow("ip", 3, 10) for _ in range(3))
    assert not rl.allow("ip", 3, 10)
    assert rl.allow("other", 3, 10)  # keys are independent
    t[0] = 10.01
    assert rl.allow("ip", 3, 10)


def test_messages():
    o = OrderView("CS-1", "Ayesha Khan", "out_for_delivery", "delivery", "2026-11-20", "10:00-13:00", D("45.5"), "USD", "Driver is on the way")
    s, b = render("status_changed", o, "Cake Studio")
    assert "out for delivery" in s and "Hi Ayesha" in b and "Driver is on the way" in b and "10:00-13:00" in b
    s, b = render("order_placed", o, "Cake Studio")
    assert "CS-1" in s and "USD 45.50" in b
