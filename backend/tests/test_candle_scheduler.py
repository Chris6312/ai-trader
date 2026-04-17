
from datetime import datetime, timezone

from app.services.candle_scheduler import next_fetch_time


def test_next_fetch_time_future():
    now = datetime(2026,1,1,0,0,10,tzinfo=timezone.utc)
    result = next_fetch_time(now,"1m")

    assert result.second == 20
