"""A tiny in-memory sliding-window rate limiter (per process)."""

from __future__ import annotations

import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, limit: int, window_seconds: float) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        """Record a hit for ``key``; ``False`` if it is over the limit."""
        if self.limit <= 0:
            return True
        now = time.monotonic()
        hits = self._hits[key]
        while hits and hits[0] <= now - self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        if len(self._hits) > 10_000:  # do not let the table grow without bound
            self._hits = defaultdict(deque, {k: v for k, v in self._hits.items() if v})
        return True
