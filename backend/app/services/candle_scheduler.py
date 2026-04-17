from __future__ import annotations

from datetime import datetime, timedelta, timezone

INTERVAL_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
}

FETCH_DELAY_SECONDS = 20


def floor_time(now: datetime, interval: str) -> datetime:
    interval_seconds = INTERVAL_SECONDS[interval]
    epoch_seconds = int(now.timestamp())
    floored_epoch = (epoch_seconds // interval_seconds) * interval_seconds
    return datetime.fromtimestamp(floored_epoch, tz=timezone.utc)


def eligible_close_time(
    now: datetime,
    interval: str,
    delay_seconds: int = FETCH_DELAY_SECONDS,
) -> datetime:
    effective_now = now - timedelta(seconds=delay_seconds)
    return floor_time(effective_now, interval)


def next_fetch_time(
    now: datetime,
    interval: str,
    delay_seconds: int = FETCH_DELAY_SECONDS,
) -> datetime:
    current_close = floor_time(now, interval)
    current_fetch = current_close + timedelta(seconds=delay_seconds)
    if now < current_fetch:
        return current_fetch

    next_close = current_close + timedelta(seconds=INTERVAL_SECONDS[interval])
    return next_close + timedelta(seconds=delay_seconds)
