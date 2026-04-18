from __future__ import annotations

from dataclasses import dataclass

from app.services.historical.schemas import RetentionBucket


_TIMEFRAME_TO_BUCKET: dict[str, RetentionBucket] = {
    "15m": "intraday_short",
    "1h": "intraday_medium",
    "4h": "swing",
    "1d": "macro",
}


def retention_bucket_for_timeframe(timeframe: str) -> RetentionBucket:
    try:
        return _TIMEFRAME_TO_BUCKET[timeframe]
    except KeyError as exc:
        raise ValueError(f"Unsupported timeframe for retention bucket: {timeframe}") from exc


@dataclass(slots=True)
class CandleRetentionPolicy:
    def bucket_for_timeframe(self, timeframe: str) -> RetentionBucket:
        return retention_bucket_for_timeframe(timeframe)