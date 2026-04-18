from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models import AssetClass


class SnapshotFilterSummaryOut(BaseModel):
    symbol: str
    asset_class: AssetClass
    timeframe: str
    candle_time: datetime
    source_label: str


class TechnicalSnapshotOut(BaseModel):
    id: int
    symbol: str
    asset_class: AssetClass
    timeframe: str
    candle_time: datetime
    source_label: str
    feature_version: str
    scoring_version: str
    technical_score: Decimal
    component_scores: dict[str, object]
    inputs: dict[str, object]
    created_at: datetime


class SentimentSnapshotOut(BaseModel):
    id: int
    symbol: str
    asset_class: AssetClass
    timeframe: str
    candle_time: datetime
    source_label: str
    input_version: str
    scoring_version: str
    sentiment_score: Decimal
    component_scores: dict[str, object]
    inputs: dict[str, object]
    created_at: datetime


class RegimeSnapshotOut(BaseModel):
    id: int
    symbol: str
    asset_class: AssetClass
    timeframe: str
    candle_time: datetime
    source_label: str
    technical_scoring_version: str
    sentiment_scoring_version: str
    detection_version: str
    regime_label: str
    regime_score: Decimal
    component_scores: dict[str, object]
    inputs: dict[str, object]
    created_at: datetime


class UniverseSnapshotOut(BaseModel):
    id: int
    symbol: str
    asset_class: AssetClass
    timeframe: str
    candle_time: datetime
    source_label: str
    technical_scoring_version: str
    sentiment_scoring_version: str
    regime_detection_version: str
    composition_version: str
    rank: int
    selected: bool
    universe_score: Decimal
    decision_label: str
    component_scores: dict[str, object]
    inputs: dict[str, object]
    created_at: datetime


class AISnapshotInspectionOut(BaseModel):
    filters: SnapshotFilterSummaryOut
    technical: TechnicalSnapshotOut | None = None
    sentiment: SentimentSnapshotOut | None = None
    regime: RegimeSnapshotOut | None = None
    universe_candidates: list[UniverseSnapshotOut]


class UniverseSnapshotListOut(BaseModel):
    rows: list[UniverseSnapshotOut]
    returned: int
    selected_only: bool
    limit: int
    candle_time: datetime | None = None
    timeframe: str | None = None
    source_label: str | None = None
    asset_class: AssetClass | None = None
