from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class BaselineModelHyperparameters:
    n_estimators: int = 100
    learning_rate: float = 0.05
    max_depth: int = 3
    min_samples_leaf: int = 1
    random_state: int = 42


@dataclass(slots=True)
class BaselineModelArtifactRecord:
    model_version: str
    model_family: str
    strategy_name: str
    dataset_version: str
    policy_version: str
    feature_version: str
    label_version: str
    feature_keys: list[str]
    label_key: str
    training_window_start: str
    training_window_end: str
    hyperparameters: dict[str, object]
    metrics: dict[str, float]
    artifact_path: str
    trained_at: datetime | None


@dataclass(slots=True)
class BaselineModelTrainingSummary:
    model_version: str | None
    model_family: str
    strategy_name: str
    dataset_version: str
    rows_considered: int
    rows_trained: int
    positive_rows: int
    negative_rows: int
    label_key: str
    feature_keys: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
    artifact_path: str | None = None
    skipped_reason: str | None = None
