from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

MLRuntimeRequestedMode = Literal["disabled", "shadow", "active_rank_only"]
MLRuntimeEffectiveMode = Literal["disabled", "shadow", "active_rank_only", "blocked"]
MLRuntimeRankingPolicy = Literal["deterministic_only", "shadow_compare", "ml_rank_only"]


@dataclass(slots=True)
class HistoricalMLRuntimeControlConfig:
    requested_mode: MLRuntimeRequestedMode = "active_rank_only"
    stale_after_days: int = 14
    require_verified_bundle: bool = True
    require_validation_reference: bool = True
    validation_metric_key: str = "roc_auc"
    minimum_validation_metric: float | None = None
    required_feature_keys: list[str] = field(default_factory=list)


@dataclass(slots=True)
class HistoricalMLRuntimeControlSummary:
    bundle_version: str
    strategy_name: str
    requested_mode: MLRuntimeRequestedMode
    effective_mode: MLRuntimeEffectiveMode
    ranking_policy: MLRuntimeRankingPolicy
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
    reason_codes: list[str] = field(default_factory=list)
    missing_feature_keys: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)
