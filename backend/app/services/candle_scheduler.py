
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


def next_fetch_time(now: datetime, interval: str) -> datetime:
    interval_sec = INTERVAL_SECONDS[interval]
    epoch = int(now.timestamp())
    next_close = (epoch // interval_sec + 1) * interval_sec
    return datetime.fromtimestamp(next_close + FETCH_DELAY_SECONDS, tz=timezone.utc)
