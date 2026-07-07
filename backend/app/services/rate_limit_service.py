"""In-memory sliding-window rate limiter for the /analyze endpoint.

Keyed by client IP for anonymous visitors and by Firebase UID for signed-in
users. State lives in process memory, which is sufficient for a single
Cloud Run instance. For multi-instance deployments this should be backed by a
shared store (e.g. Firestore or Memorystore/Redis); the public API here is kept
small so that swap is straightforward.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset_after: int  # seconds until the current window resets


class SlidingWindowRateLimiter:
    def __init__(self, window_seconds: int) -> None:
        self._window = max(1, window_seconds)
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str, limit: int) -> RateLimitResult:
        """Record a hit for ``key`` and report whether it is within ``limit``."""
        now = time.time()
        cutoff = now - self._window

        with self._lock:
            # Keys that never return would otherwise accumulate forever.
            # ponytail: O(total keys) sweep, fine at this traffic level.
            if len(self._hits) > 1024:
                self._evict_expired(now)
            timestamps = self._hits.get(key, [])
            # Drop hits that fall outside the current window.
            timestamps = [t for t in timestamps if t > cutoff]

            if len(timestamps) >= limit:
                oldest = min(timestamps)
                reset_after = int(self._window - (now - oldest)) + 1
                self._hits[key] = timestamps
                return RateLimitResult(
                    allowed=False,
                    limit=limit,
                    remaining=0,
                    reset_after=max(1, reset_after),
                )

            timestamps.append(now)
            self._hits[key] = timestamps
            return RateLimitResult(
                allowed=True,
                limit=limit,
                remaining=max(0, limit - len(timestamps)),
                reset_after=self._window,
            )

    def _evict_expired(self, now: float) -> None:
        cutoff = now - self._window
        empty_keys = []
        for key, timestamps in self._hits.items():
            kept = [t for t in timestamps if t > cutoff]
            if kept:
                self._hits[key] = kept
            else:
                empty_keys.append(key)
        for key in empty_keys:
            self._hits.pop(key, None)


_limiter: SlidingWindowRateLimiter | None = None


def get_limiter(window_seconds: int) -> SlidingWindowRateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = SlidingWindowRateLimiter(window_seconds)
    return _limiter
