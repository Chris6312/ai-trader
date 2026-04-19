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


class MLTransparencyModelOut(BaseModel):
    bundle_version: str
    bundle_name: str
    model_version: str
    model_family: str
    dataset_version: str
    strategy_name: str
    label_key: str
    feature_count: int
    manifest_path: str
    created_at: str | None = None
    validation_version: str | None = None
    drift_report_version: str | None = None
    scoring_version: str | None = None
    verified_artifact: bool


class MLRuntimeControlOut(BaseModel):
    bundle_version: str
    strategy_name: str
    requested_mode: str
    effective_mode: str
    ranking_policy: str
    ml_scoring_allowed: bool
    ml_influence_allowed: bool
    deterministic_fallback_active: bool
    verified_artifact: bool
    validation_reference_present: bool
    bundle_age_days: int | None = None
    stale_after_days: int | None = None
    validation_metric_key: str | None = None
    validation_metric_value: float | None = None
    evaluated_at: datetime | None = None
    reason_codes: list[str]
    missing_feature_keys: list[str]
    metadata: dict[str, object]


class MLTransparencyFeatureOut(BaseModel):
    feature_key: str
    tree_importance: float | None = None
    permutation_importance: float | None = None
    standardized_mean_shift: float | None = None
    population_stability_index: float | None = None
    drift_flagged: bool = False
    direction: str | None = None
    contribution: float | None = None
    feature_value: float | None = None
    baseline_value: float | None = None


class MLTransparencyRowReferenceOut(BaseModel):
    row_key: str
    symbol: str
    asset_class: str
    timeframe: str
    decision_date: str
    entry_candle_time: str
    strategy_name: str


class MLTransparencyModelRegistryOut(BaseModel):
    rows: list[MLTransparencyModelOut]
    returned: int


class MLTransparencyOverviewOut(BaseModel):
    model: MLTransparencyModelOut
    lineage: dict[str, object]
    training_metrics: dict[str, float]
    global_feature_importance: list[MLTransparencyFeatureOut]
    regime_feature_importance: list[MLTransparencyFeatureOut]
    drift_signals: list[MLTransparencyFeatureOut]
    health: dict[str, object]
    sample_rows: list[MLTransparencyRowReferenceOut]


class MLTransparencyRowListOut(BaseModel):
    rows: list[MLTransparencyRowReferenceOut]
    returned: int


class MLTransparencyFeatureHealthPanelOut(BaseModel):
    bundle_version: str
    model_version: str
    dataset_version: str
    strategy_name: str
    runtime_control: MLRuntimeControlOut | None = None
    validation_summary: dict[str, object]
    drift_summary: dict[str, object]
    global_feature_leaders: list[MLTransparencyFeatureOut]
    regime_feature_leaders: list[MLTransparencyFeatureOut]
    overlapping_feature_keys: list[str]


class MLTransparencyExplanationOut(BaseModel):
    bundle_version: str
    model_version: str
    dataset_version: str
    strategy_name: str
    row: MLTransparencyRowReferenceOut
    score: float | None = None
    probability: float | None = None
    confidence: float | None = None
    baseline_expectation: dict[str, float]
    positive_contributors: list[MLTransparencyFeatureOut]
    negative_contributors: list[MLTransparencyFeatureOut]
    feature_snapshot: dict[str, object]
    skipped_reason: str | None = None


class MLTransparencyStrategyLearningPanelOut(BaseModel):
    bundle_version: str
    model_version: str
    dataset_version: str
    strategy_name: str
    runtime_control: MLRuntimeControlOut | None = None
    summary: dict[str, object]
    global_feature_importance: list[MLTransparencyFeatureOut]
    regime_feature_importance: list[MLTransparencyFeatureOut]
    drift_signals: list[MLTransparencyFeatureOut]
    highlighted_rows: list[MLTransparencyRowReferenceOut]
