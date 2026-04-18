from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.services.historical.schemas import AssetClass, HistoricalSource, SupportedTimeframe


@dataclass(slots=True)
class TechnicalScoreRecord:
    symbol: str
    asset_class: AssetClass
    timeframe: SupportedTimeframe
    candle_time: datetime
    source_label: HistoricalSource
    feature_version: str
    scoring_version: str
    technical_score: Decimal
    component_scores: dict[str, Decimal]
    inputs: dict[str, Decimal]


@dataclass(slots=True)
class TechnicalScoreSummary:
    symbol: str
    asset_class: AssetClass
    timeframe: SupportedTimeframe
    source_label: HistoricalSource
    rows_input: int
    rows_scored: int
    scoring_version: str
    feature_version: str
