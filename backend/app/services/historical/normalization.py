from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.models import AssetClass
from app.services.historical.retention import retention_bucket_for_timeframe
from app.services.historical.schemas import HistoricalCandleRecord

_TIMEFRAME_MAP = {
    "15m": "15Min",
    "1h": "1Hour",
    "4h": "4Hour",
    "1d": "1Day",
}


def alpaca_timeframe_for(timeframe: str) -> str:
    try:
        return _TIMEFRAME_MAP[timeframe]
    except KeyError as exc:
        raise ValueError(f"Unsupported timeframe: {timeframe}") from exc


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def normalize_stock_symbol(symbol: str) -> str:
    cleaned = symbol.strip().upper()
    if not cleaned:
        raise ValueError("symbol cannot be empty")
    return cleaned


def _to_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def normalize_alpaca_bar(*, symbol: str, timeframe: str, bar: dict[str, Any], fetched_at: datetime) -> HistoricalCandleRecord:
    ts_value = bar.get("t")
    if ts_value is None:
        raise ValueError("Alpaca bar missing timestamp 't'")

    if isinstance(ts_value, str):
        ts = datetime.fromisoformat(ts_value.replace("Z", "+00:00"))
    elif isinstance(ts_value, datetime):
        ts = ts_value
    else:
        raise ValueError("Unsupported timestamp type for Alpaca bar")

    return HistoricalCandleRecord(
        symbol=normalize_stock_symbol(symbol),
        asset_class=AssetClass.STOCK,
        timeframe=timeframe,
        candle_time=ensure_utc(ts),
        open=_to_decimal(bar["o"]),
        high=_to_decimal(bar["h"]),
        low=_to_decimal(bar["l"]),
        close=_to_decimal(bar["c"]),
        volume=_to_decimal(bar.get("v", 0)),
        source_label="alpaca",
        retention_bucket=retention_bucket_for_timeframe(timeframe),
        fetched_at=ensure_utc(fetched_at),
    )
