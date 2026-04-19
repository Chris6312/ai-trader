from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from app.models.trading import AssetClass


@dataclass(slots=True)
class FeatureDefinitionVersionRecord:
    feature_version: str
    feature_keys: list[str]
    warmup_period: int
    created_at: datetime


@dataclass(slots=True)
class HistoricalFeatureStoreRowRecord:
    decision_date: date
    symbol: str
    asset_class: AssetClass
    timeframe: str
    candle_time: datetime
    source_label: str
    feature_version: str
    values: dict[str, object]


@dataclass(slots=True)
class HistoricalFeatureStoreBuildSummary:
    decision_date: date
    asset_class: str
    timeframe: str
    source_label: str
    symbols_requested: int
    symbols_built: int
    rows_inserted: int
    rows_replaced: int
    feature_version: str
