from __future__ import annotations

from dataclasses import dataclass, field

from app.services.historical.historical_walkforward_validation_schemas import HistoricalWalkForwardValidationConfig


@dataclass(slots=True)
class HistoricalFeatureImportanceReviewConfig:
    report_version_prefix: str = "12i_v1"
    validation_config: HistoricalWalkForwardValidationConfig = field(
        default_factory=HistoricalWalkForwardValidationConfig
    )
    permutation_repeats: int = 5
    drift_psi_threshold: float = 0.2
    drift_mean_shift_threshold: float = 0.5
    top_feature_count: int = 10


@dataclass(slots=True)
class FeatureImportanceRecord:
    feature_key: str
    tree_importance: float
    permutation_importance: float
    folds_observed: int
    mean_rank: float


@dataclass(slots=True)
class FeatureDriftRecord:
    feature_key: str
    population_stability_index: float
    standardized_mean_shift: float
    train_mean: float
    validation_mean: float
    train_std: float
    validation_std: float
    drift_flagged: bool
    drift_flag_reasons: list[str] = field(default_factory=list)


@dataclass(slots=True)
class FeatureImportanceFoldReview:
    fold_index: int
    train_start_date: str
    train_end_date: str
    validation_start_date: str
    validation_end_date: str
    train_row_count: int
    validation_row_count: int
    skipped_reason: str | None = None
    feature_importance: list[FeatureImportanceRecord] = field(default_factory=list)
    drift_metrics: list[FeatureDriftRecord] = field(default_factory=list)


@dataclass(slots=True)
class HistoricalFeatureImportanceReviewSummary:
    report_version: str
    dataset_version: str
    strategy_name: str
    model_family: str
    validation_version: str
    feature_keys: list[str] = field(default_factory=list)
    global_feature_importance: list[FeatureImportanceRecord] = field(default_factory=list)
    regime_feature_importance: list[FeatureImportanceRecord] = field(default_factory=list)
    global_drift_metrics: list[FeatureDriftRecord] = field(default_factory=list)
    drifted_features: list[FeatureDriftRecord] = field(default_factory=list)
    folds: list[FeatureImportanceFoldReview] = field(default_factory=list)
    artifact_path: str | None = None
