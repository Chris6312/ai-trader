from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


_TIMEFRAME_TO_DELTA: dict[str, timedelta] = {
    "1m": timedelta(minutes=1),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "30m": timedelta(minutes=30),
    "1h": timedelta(hours=1),
    "4h": timedelta(hours=4),
    "1d": timedelta(days=1),
}


@dataclass(slots=True)
class BackfillPlan:
    symbol: str
    asset_class: str
    timeframe: str
    fetch_start_at: datetime | None
    fetch_end_at: datetime
    should_fetch: bool
    reason: str


class BackfillPlanner:
    def plan_incremental(
        self,
        *,
        symbol: str,
        asset_class: str,
        timeframe: str,
        latest_candle_ts: datetime | None,
        bootstrap_start_at: datetime | None = None,
        requested_end_at: datetime,
    ) -> BackfillPlan:
        normalized_end_at = self._coerce_utc(requested_end_at)

        if latest_candle_ts is None:
            normalized_bootstrap = self._coerce_optional_utc(bootstrap_start_at)
            if normalized_bootstrap is None:
                return BackfillPlan(
                    symbol=symbol,
                    asset_class=asset_class,
                    timeframe=timeframe,
                    fetch_start_at=None,
                    fetch_end_at=normalized_end_at,
                    should_fetch=False,
                    reason="missing_bootstrap_start",
                )

            return BackfillPlan(
                symbol=symbol,
                asset_class=asset_class,
                timeframe=timeframe,
                fetch_start_at=normalized_bootstrap,
                fetch_end_at=normalized_end_at,
                should_fetch=True,
                reason="empty_history",
            )

        normalized_latest = self._coerce_utc(latest_candle_ts)
        candle_delta = self._timeframe_delta(timeframe)
        next_expected_candle_at = normalized_latest + candle_delta

        if next_expected_candle_at >= normalized_end_at:
            return BackfillPlan(
                symbol=symbol,
                asset_class=asset_class,
                timeframe=timeframe,
                fetch_start_at=normalized_end_at,
                fetch_end_at=normalized_end_at,
                should_fetch=False,
                reason="already_current",
            )

        return BackfillPlan(
            symbol=symbol,
            asset_class=asset_class,
            timeframe=timeframe,
            fetch_start_at=next_expected_candle_at,
            fetch_end_at=normalized_end_at,
            should_fetch=True,
            reason="incremental_gap",
        )

    @staticmethod
    def _coerce_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @classmethod
    def _coerce_optional_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return cls._coerce_utc(value)

    @staticmethod
    def _timeframe_delta(timeframe: str) -> timedelta:
        try:
            return _TIMEFRAME_TO_DELTA[timeframe]
        except KeyError as exc:
            raise ValueError(f"unsupported timeframe: {timeframe}") from exc