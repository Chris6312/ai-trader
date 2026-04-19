from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from app.models.trading import AssetClass


@dataclass(slots=True)
class HistoricalTrainingDataset:
    dataset_name: str
    dataset_definition_version: str
    policy_version: str
    feature_version: str
    asset_class: str
    timeframe: str
    start_date: date
    end_date: date


@dataclass(slots=True)
class TrainingDatasetVersionRecord:
    dataset_version: str
    dataset_name: str
    dataset_definition_version: str
    asset_class: AssetClass
    timeframe: str
    source_label: str | None
    strategy_name: str | None
    start_date: date
    end_date: date
    policy_version: str
    feature_version: str
    replay_version: str
    label_version: str
    row_count: int
    feature_keys: list[str]
    build_metadata: dict[str, object]
    created_at: datetime


@dataclass(slots=True)
class TrainingDatasetRowRecord:
    dataset_version: str
    row_key: str
    decision_date: date
    symbol: str
    asset_class: AssetClass
    timeframe: str
    strategy_name: str
    source_label: str
    entry_candle_time: datetime
    feature_version: str
    replay_version: str
    label_version: str
    feature_values: dict[str, object]
    label_values: dict[str, object]
    metadata: dict[str, object]


@dataclass(slots=True)
class TrainingDatasetBuildSummary:
    dataset_version: str
    dataset_name: str
    dataset_definition_version: str
    asset_class: str
    timeframe: str
    source_label: str | None
    strategy_name: str | None
    policy_version: str
    feature_version: str
    replay_version: str
    label_version: str
    start_date: date
    end_date: date
    rows_considered: int
    rows_built: int
    rows_replaced: int
    rows_skipped_missing_universe: int
    rows_skipped_missing_feature: int
    rows_skipped_missing_label: int
