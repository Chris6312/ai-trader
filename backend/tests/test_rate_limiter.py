from __future__ import annotations

from app.services.historical.rate_limiter import RateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def test_rate_limiter_allows_calls_within_capacity() -> None:
    clock = FakeClock()
    limiter = RateLimiter(
        max_calls=3,
        period_seconds=60.0,
        clock=clock.monotonic,
        sleep=clock.sleep,
    )

    limiter.acquire()
    limiter.acquire()
    limiter.acquire()

    assert clock.sleeps == []


def test_rate_limiter_sleeps_when_capacity_is_exhausted() -> None:
    clock = FakeClock()
    limiter = RateLimiter(
        max_calls=2,
        period_seconds=60.0,
        clock=clock.monotonic,
        sleep=clock.sleep,
    )

    limiter.acquire()
    limiter.acquire()
    limiter.acquire()

    assert clock.sleeps == [60.0]


def test_rate_limiter_releases_capacity_after_window_moves() -> None:
    clock = FakeClock()
    limiter = RateLimiter(
        max_calls=1,
        period_seconds=10.0,
        clock=clock.monotonic,
        sleep=clock.sleep,
    )

    limiter.acquire()   # t=0.0
    limiter.acquire()   # waits 10.0s, granted at t=10.0
    clock.now += 0.1    # t=10.1
    limiter.acquire()   # waits 9.9s, granted at t=20.0

    assert clock.sleeps == [10.0, 9.9]


def test_rate_limiter_discards_expired_calls_from_window() -> None:
    clock = FakeClock()
    limiter = RateLimiter(
        max_calls=2,
        period_seconds=10.0,
        clock=clock.monotonic,
        sleep=clock.sleep,
    )

    limiter.acquire()   # t=0.0
    limiter.acquire()   # t=0.0
    clock.now = 10.1    # both old calls are expired
    limiter.acquire()

    assert clock.sleeps == []


def test_rate_limiter_rejects_non_positive_max_calls() -> None:
    try:
        RateLimiter(max_calls=0, period_seconds=60.0)
    except ValueError as exc:
        assert "max_calls" in str(exc)
    else:
        raise AssertionError("Expected ValueError for non-positive max_calls")


def test_rate_limiter_rejects_non_positive_period_seconds() -> None:
    try:
        RateLimiter(max_calls=1, period_seconds=0.0)
    except ValueError as exc:
        assert "period_seconds" in str(exc)
    else:
        raise AssertionError("Expected ValueError for non-positive period_seconds")