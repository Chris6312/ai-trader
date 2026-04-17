from datetime import datetime, timezone

from app.services.candle_scheduler import eligible_close_time, next_fetch_time


def test_next_fetch_time_uses_post_close_delay() -> None:
    now = datetime(2026, 1, 1, 0, 0, 10, tzinfo=timezone.utc)
    result = next_fetch_time(now, "1m")

    assert result == datetime(2026, 1, 1, 0, 0, 20, tzinfo=timezone.utc)


def test_eligible_close_time_points_to_latest_closed_slot() -> None:
    now = datetime(2026, 1, 1, 10, 5, 21, tzinfo=timezone.utc)
    result = eligible_close_time(now, "5m")

    assert result == datetime(2026, 1, 1, 10, 5, 0, tzinfo=timezone.utc)
