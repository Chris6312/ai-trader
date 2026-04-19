from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(slots=True)
class HistoricalWalkForwardValidationConfig:
    validation_version_prefix: str = "12h_v1"
    split_mode: str = "anchored"
    min_train_periods: int = 5
    validation_periods: int = 2
    step_periods: int = 2
    rolling_train_periods: int | None = None
    label_key: str = "achieved_label"


@dataclass(slots=True)
class WalkForwardFoldPlan:
    fold_index: int
    train_start_date: date
    train_end_date: date
    validation_start_date: date
    validation_end_date: date
    train_row_count: int
    validation_row_count: int
    skipped_reason: str | None = None


@dataclass(slots=True)
class WalkForwardFoldResult:
    fold_index: int
    train_start_date: date
    train_end_date: date
    validation_start_date: date
    validation_end_date: date
    train_row_count: int
    validation_row_count: int
    positive_rows: int
    negative_rows: int
    feature_keys: list[str]
    metrics: dict[str, float]
    skipped_reason: str | None = None


@dataclass(slots=True)
class WalkForwardAggregateMetrics:
    folds_attempted: int
    folds_completed: int
    folds_skipped: int
    rows_validated: int
    accuracy: float | None = None
    precision: float | None = None
    recall: float | None = None
    roc_auc: float | None = None
    validation_positive_rate: float | None = None


@dataclass(slots=True)
class HistoricalWalkForwardValidationSummary:
    validation_version: str
    dataset_version: str
    strategy_name: str
    model_family: str
    split_mode: str
    label_key: str
    folds: list[WalkForwardFoldResult] = field(default_factory=list)
    aggregate_metrics: WalkForwardAggregateMetrics | None = None
