from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.models import CandleInterval


EASTERN_TZ = ZoneInfo("America/New_York")
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 30
MARKET_CLOSE_HOUR = 16
MARKET_CLOSE_MINUTE = 0


def to_eastern(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(EASTERN_TZ)


def is_trading_day(value: datetime) -> bool:
    eastern = to_eastern(value)
    return eastern.weekday() < 5


def is_stock_market_closed(value: datetime) -> bool:
    eastern = to_eastern(value)
    if eastern.weekday() >= 5:
        return True

    market_close = eastern.replace(
        hour=MARKET_CLOSE_HOUR,
        minute=MARKET_CLOSE_MINUTE,
        second=0,
        microsecond=0,
    )
    return eastern >= market_close


def should_fetch_stock_candles(
    *,
    interval: CandleInterval,
    as_of: datetime,
    backfill: bool = False,
) -> bool:
    if backfill:
        return True

    if interval != CandleInterval.DAY_1:
        return False

    return is_stock_market_closed(as_of)
