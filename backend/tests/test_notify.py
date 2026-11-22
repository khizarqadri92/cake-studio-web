from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.services.outbox_rules import MAX_ATTEMPTS, apply_result

NOW = datetime(2026, 11, 18, tzinfo=timezone.utc)


@dataclass
class N:
    attempts: int = 0
    status: str = "pending"
    last_error: str | None = None
    sent_at: datetime | None = None
    next_attempt_at: datetime = NOW


def test_success():
    n = N(attempts=1, last_error="x")
    apply_result(n, True, None, NOW)
    assert (n.status, n.attempts, n.last_error, n.sent_at) == ("sent", 2, None, NOW)


def test_retry_backoff_then_fail():
    n = N()
    apply_result(n, False, "boom", NOW)
    assert n.status == "pending" and n.next_attempt_at == NOW + timedelta(minutes=2) and n.last_error == "boom"
    apply_result(n, False, "boom", NOW)
    assert n.next_attempt_at == NOW + timedelta(minutes=4)
    for _ in range(MAX_ATTEMPTS):
        apply_result(n, False, "x" * 900, NOW)
    assert n.status == "failed" and len(n.last_error) == 500
