from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

from app.services.historical.schemas import AssetClass, HistoricalSource, SupportedTimeframe

RegimeLabel = Literal["risk_on", "neutral", "risk_off"]


@dataclass(slots=True)
class RegimeDetectionRecord:
    symbol: str
    asset_class: AssetClass
    timeframe: SupportedTimeframe
    candle_time: datetime
    source_label: HistoricalSource
    technical_scoring_version: str
    sentiment_scoring_version: str
    detection_version: str
    regime_label: RegimeLabel
    regime_score: Decimal
    component_scores: dict[str, Decimal]
    inputs: dict[str, Decimal]


@dataclass(slots=True)
class RegimeDetectionSummary:
    symbol: str
    asset_class: AssetClass
    timeframe: SupportedTimeframe
    source_label: HistoricalSource
    rows_technical_input: int
    rows_sentiment_input: int
    rows_classified: int
    detection_version: str
    technical_scoring_version: str
    sentiment_scoring_version: str
