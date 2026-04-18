from __future__ import annotations

import threading
import time
from collections import deque
from typing import Callable


class RateLimiter:
    def __init__(
        self,
        *,
        max_calls: int,
        period_seconds: float = 60.0,
        clock: Callable[[], float] | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        if max_calls <= 0:
            raise ValueError("max_calls must be greater than zero")
        if period_seconds <= 0:
            raise ValueError("period_seconds must be greater than zero")
        self._max_calls = max_calls
        self._period_seconds = period_seconds
        self._clock = clock or time.monotonic
        self._sleep = sleep or time.sleep
        self._calls: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        while True:
            with self._lock:
                now = self._clock()
                self._trim(now)
                if len(self._calls) < self._max_calls:
                    self._calls.append(now)
                    return
                wait_seconds = self._period_seconds - (now - self._calls[0])
            self._sleep(max(wait_seconds, 0.0))

    def _trim(self, now: float) -> None:
        cutoff = now - self._period_seconds
        while self._calls and self._calls[0] <= cutoff:
            self._calls.popleft()
