from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.services.historical.schemas import AssetClass, HistoricalSource, SupportedTimeframe


@dataclass(slots=True)
class UniverseCandidateRecord:
    symbol: str
    asset_class: AssetClass
    timeframe: SupportedTimeframe
    candle_time: datetime
    source_label: HistoricalSource
    technical_scoring_version: str
    sentiment_scoring_version: str
    regime_detection_version: str
    composition_version: str
    rank: int
    selected: bool
    universe_score: Decimal
    decision_label: str
    component_scores: dict[str, Decimal]
    inputs: dict[str, Decimal]


@dataclass(slots=True)
class UniverseCompositionSummary:
    rows_technical_input: int
    rows_sentiment_input: int
    rows_regime_input: int
    rows_eligible: int
    rows_composed: int
    rows_selected: int
    composition_version: str
    technical_scoring_version: str | None
    sentiment_scoring_version: str | None
    regime_detection_version: str | None
