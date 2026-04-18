from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.services.historical.schemas import BackfillPlan


_TIMEFRAME_DELTAS: dict[str, timedelta] = {
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "4h": timedelta(hours=4),
    "1d": timedelta(days=1),
}


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class BackfillPlanner:
    def plan_incremental(
        self,
        *,
        symbol: str,
        asset_class: str,
        timeframe: str,
        latest_candle_ts: datetime | None,
        requested_end_at: datetime,
        bootstrap_start_at: datetime | None = None,
    ) -> BackfillPlan:
        if timeframe not in _TIMEFRAME_DELTAS:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        end_at = _ensure_utc(requested_end_at)

        if latest_candle_ts is None:
            if bootstrap_start_at is None:
                return BackfillPlan(
                    symbol=symbol,
                    asset_class=asset_class,
                    timeframe=timeframe,
                    fetch_start_at=None,
                    fetch_end_at=end_at,
                    should_fetch=False,
                    reason="missing_bootstrap_start",
                )

            start_at = _ensure_utc(bootstrap_start_at)
            if start_at >= end_at:
                return BackfillPlan(
                    symbol=symbol,
                    asset_class=asset_class,
                    timeframe=timeframe,
                    fetch_start_at=None,
                    fetch_end_at=end_at,
                    should_fetch=False,
                    reason="already_current",
                )

            return BackfillPlan(
                symbol=symbol,
                asset_class=asset_class,
                timeframe=timeframe,
                fetch_start_at=start_at,
                fetch_end_at=end_at,
                should_fetch=True,
                reason="empty_history",
            )

        next_start = _ensure_utc(latest_candle_ts) + _TIMEFRAME_DELTAS[timeframe]
        if next_start >= end_at:
            return BackfillPlan(
                symbol=symbol,
                asset_class=asset_class,
                timeframe=timeframe,
                fetch_start_at=None,
                fetch_end_at=end_at,
                should_fetch=False,
                reason="already_current",
            )

        return BackfillPlan(
            symbol=symbol,
            asset_class=asset_class,
            timeframe=timeframe,
            fetch_start_at=next_start,
            fetch_end_at=end_at,
            should_fetch=True,
            reason="incremental_gap",
        )