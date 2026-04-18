from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

AssetClass = Literal["stock", "crypto"]
SupportedTimeframe = Literal["15m", "1h", "4h", "1d"]
HistoricalSource = Literal["alpaca", "kraken_csv"]
RetentionBucket = Literal[
    "intraday_short",
    "intraday_medium",
    "swing",
    "macro",
]


@dataclass(slots=True)
class HistoricalCandleRecord:
    symbol: str
    asset_class: AssetClass
    timeframe: SupportedTimeframe
    candle_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    source_label: HistoricalSource
    fetched_at: datetime
    retention_bucket: RetentionBucket


@dataclass(slots=True)
class HistoricalBackfillRequest:
    symbol: str
    asset_class: AssetClass
    timeframe: SupportedTimeframe
    start_at: datetime | None = None
    end_at: datetime | None = None


@dataclass(slots=True)
class BackfillPlan:
    symbol: str
    asset_class: AssetClass
    timeframe: SupportedTimeframe
    fetch_start_at: datetime | None
    fetch_end_at: datetime
    should_fetch: bool
    reason: str


@dataclass(slots=True)
class IngestionSummary:
    symbol: str
    asset_class: AssetClass
    timeframe: SupportedTimeframe
    source_label: HistoricalSource
    rows_read: int
    rows_inserted: int
    rows_skipped_duplicate: int
    rows_skipped_out_of_range: int