from datetime import datetime, timezone

from app.models import CandleInterval
from app.services.market_clock import (
    is_stock_market_closed,
    should_fetch_stock_candles,
    to_eastern,
)


def test_market_clock_converts_to_eastern() -> None:
    value = datetime(2026, 4, 17, 20, 5, tzinfo=timezone.utc)
    eastern = to_eastern(value)

    assert eastern.tzinfo is not None
    assert eastern.hour == 16
    assert eastern.minute == 5


def test_stock_market_closed_after_4pm_eastern() -> None:
    assert is_stock_market_closed(datetime(2026, 4, 17, 20, 5, tzinfo=timezone.utc)) is True
    assert is_stock_market_closed(datetime(2026, 4, 17, 19, 55, tzinfo=timezone.utc)) is False


def test_should_fetch_stock_candles_requires_daily_close_unless_backfill() -> None:
    before_close = datetime(2026, 4, 17, 19, 55, tzinfo=timezone.utc)

    assert should_fetch_stock_candles(
        interval=CandleInterval.DAY_1,
        as_of=before_close,
        backfill=False,
    ) is False
    assert should_fetch_stock_candles(
        interval=CandleInterval.MINUTE_5,
        as_of=datetime(2026, 4, 17, 20, 5, tzinfo=timezone.utc),
        backfill=False,
    ) is False
    assert should_fetch_stock_candles(
        interval=CandleInterval.MINUTE_5,
        as_of=before_close,
        backfill=True,
    ) is True
