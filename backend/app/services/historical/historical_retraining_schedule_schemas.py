from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass(slots=True)
class HistoricalRetrainingScheduleConfig:
    schedule_version_prefix: str = "12k_v1"
    cadence: str = "weekly"
    timezone_name: str = "America/New_York"
    scheduled_day_of_week: int = 5
    scheduled_time: str = "08:40"
    min_days_between_runs: int = 7
    min_new_rows: int = 20
    force_retrain_on_drift: bool = True
    drifted_feature_threshold: int = 2
    force_retrain_on_validation_drop: bool = True
    min_acceptable_roc_auc: float = 0.52


@dataclass(slots=True)
class HistoricalRetrainingContext:
    now: datetime
    latest_dataset_version: str
    latest_dataset_end_date: date
    latest_row_count: int
    latest_strategy_name: str
    active_model_version: str | None = None
    active_dataset_version: str | None = None
    active_dataset_end_date: date | None = None
    active_dataset_row_count: int | None = None
    active_model_trained_at: datetime | None = None
    last_validation_version: str | None = None
    last_validation_roc_auc: float | None = None
    last_drift_report_version: str | None = None
    drifted_feature_count: int = 0
    manual_trigger: bool = False


@dataclass(slots=True)
class RetrainingPipelineStep:
    step_key: str
    title: str
    required: bool
    description: str


@dataclass(slots=True)
class HistoricalRetrainingScheduleSummary:
    schedule_version: str
    should_retrain: bool
    reason: str
    cadence: str
    strategy_name: str
    scheduled_for: datetime
    latest_dataset_version: str
    active_model_version: str | None
    latest_row_count: int
    new_rows_available: int
    drift_triggered: bool
    validation_triggered: bool
    guardrails: list[str] = field(default_factory=list)
    pipeline_steps: list[RetrainingPipelineStep] = field(default_factory=list)
