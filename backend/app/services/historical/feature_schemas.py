from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.services.historical.schemas import AssetClass, HistoricalSource, SupportedTimeframe


@dataclass(slots=True)
class HistoricalFeatureRecord:
    symbol: str
    asset_class: AssetClass
    timeframe: SupportedTimeframe
    candle_time: datetime
    source_label: HistoricalSource
    feature_version: str
    values: dict[str, Decimal]


@dataclass(slots=True)
class FeatureBuildSummary:
    symbol: str
    asset_class: AssetClass
    timeframe: SupportedTimeframe
    source_label: HistoricalSource
    rows_input: int
    rows_output: int
    warmup_rows_skipped: int
    feature_version: str
