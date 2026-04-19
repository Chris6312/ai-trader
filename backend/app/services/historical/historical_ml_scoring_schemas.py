from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.services.historical.historical_ml_runtime_controls_schemas import HistoricalMLRuntimeControlSummary


@dataclass(slots=True)
class HistoricalMLScoringConfig:
    scoring_version_prefix: str = "12j_v1"
    base_score_weight: float = 0.65
    ml_score_weight: float = 0.35
    top_explanation_count: int = 3


@dataclass(slots=True)
class MLScoringCandidateInput:
    symbol: str
    asset_class: str
    timeframe: str
    candle_time: datetime
    source_label: str
    strategy_name: str
    base_rank: int
    base_score: float
    feature_values: dict[str, float]
    eligible: bool = True
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class MLScoreExplanationRecord:
    feature_key: str
    feature_value: float
    baseline_value: float
    importance_weight: float
    signed_contribution: float


@dataclass(slots=True)
class MLScoredCandidateRecord:
    symbol: str
    asset_class: str
    timeframe: str
    candle_time: datetime
    source_label: str
    strategy_name: str
    base_rank: int
    final_rank: int
    base_score: float
    combined_score: float
    ml_probability: float | None
    ml_confidence: float | None
    model_version: str | None
    scoring_skipped_reason: str | None = None
    explanation: list[MLScoreExplanationRecord] = field(default_factory=list)
    runtime_reason_codes: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class HistoricalMLScoringSummary:
    scoring_version: str
    strategy_name: str
    dataset_version: str
    model_version: str | None
    model_family: str | None
    feature_keys: list[str]
    rows_input: int
    rows_scored: int
    rows_skipped: int
    bundle_version: str | None = None
    runtime_control: HistoricalMLRuntimeControlSummary | None = None
    candidates: list[MLScoredCandidateRecord] = field(default_factory=list)
