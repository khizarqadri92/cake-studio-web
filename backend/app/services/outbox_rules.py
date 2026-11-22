"""Pure retry rules for the notification outbox."""
from datetime import datetime, timedelta

MAX_ATTEMPTS = 3


def apply_result(n, ok: bool, error: str | None, now: datetime) -> None:
    """Pure state update for one delivery attempt (exponential backoff, give up after MAX_ATTEMPTS)."""
    n.attempts += 1
    if ok:
        n.status, n.sent_at, n.last_error = "sent", now, None
        return
    n.last_error = (error or "unknown error")[:500]
    if n.attempts >= MAX_ATTEMPTS:
        n.status = "failed"
    else:
        n.next_attempt_at = now + timedelta(minutes=2 ** n.attempts)
