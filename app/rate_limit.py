"""
Rate limiting, keyed per agent_id (not per API key -- one agent misbehaving
shouldn't need its own key to be throttled, and one deployment key might be
shared across many agents).

Implementation: a fixed-window counter per agent_id, reset every
`window_seconds`. This is intentionally in-memory and process-local.

Production note: this does NOT work correctly if you run more than one
proxy replica behind a load balancer -- each replica has its own counters,
so effective limits multiply by replica count. For horizontal scaling,
swap the in-memory dict below for Redis (INCR + EXPIRE per key), which is
a small, mechanical change since callers only depend on
`RateLimiter.check(agent_id) -> bool`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from fastapi import HTTPException, status

from app.config import settings


@dataclass
class _Window:
    count: int = 0
    window_start: float = field(default_factory=time.time)


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._windows: dict[str, _Window] = {}

    def check(self, key: str) -> bool:
        """Returns True if the request is allowed, False if rate-limited."""
        now = time.time()
        window = self._windows.get(key)

        if window is None or (now - window.window_start) >= self.window_seconds:
            self._windows[key] = _Window(count=1, window_start=now)
            return True

        if window.count >= self.max_requests:
            return False

        window.count += 1
        return True

    def reset(self) -> None:
        """Used by tests to avoid state leaking between test cases."""
        self._windows.clear()


rate_limiter = RateLimiter(
    max_requests=settings.rate_limit_requests,
    window_seconds=settings.rate_limit_window_seconds,
)


def enforce_rate_limit(agent_id: str) -> None:
    if not rate_limiter.check(agent_id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Rate limit exceeded: max {rate_limiter.max_requests} requests "
                f"per {rate_limiter.window_seconds}s per agent"
            ),
        )
