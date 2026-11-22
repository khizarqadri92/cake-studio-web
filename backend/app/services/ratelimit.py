"""Sliding-window rate limiter. In-process, so limits are per worker; swap `_hits` for Redis when running
several replicas (documented in docs/SECURITY.md)."""
import time
from collections import defaultdict, deque
from threading import Lock


class RateLimiter:
    def __init__(self, clock=time.monotonic):
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()
        self._clock = clock

    def allow(self, key: str, limit: int, window_s: float) -> bool:
        now = self._clock()
        with self._lock:
            q = self._hits[key]
            while q and q[0] <= now - window_s:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            if len(self._hits) > 50_000:  # bound memory under a key-spraying attack
                for k in [k for k, v in self._hits.items() if not v or v[-1] <= now - window_s][:10_000]:
                    self._hits.pop(k, None)
            return True


limiter = RateLimiter()
