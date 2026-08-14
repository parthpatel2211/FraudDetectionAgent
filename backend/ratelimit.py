from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    """Sliding-window limiter, scoped to one process.

    This is a speed bump, not a guarantee. Serverless instances do not share
    state, so a client hitting several cold instances gets several budgets. The
    real cost ceiling is the spend limit configured on the Anthropic API key -
    this only stops one caller from hammering a single warm instance.

    `per_minute <= 0` disables limiting entirely, which is what local
    development and the test suite run with.
    """

    def __init__(self, per_minute: int) -> None:
        self.per_minute = per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        if self.per_minute <= 0:
            return True
        now = time.monotonic()
        with self._lock:
            window = self._hits[key]
            while window and now - window[0] > 60:
                window.popleft()
            if len(window) >= self.per_minute:
                return False
            window.append(now)
            return True
