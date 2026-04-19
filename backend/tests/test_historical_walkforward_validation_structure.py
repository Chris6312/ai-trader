from __future__ import annotations

from app.services.historical import (
    HistoricalWalkForwardValidationConfig,
    HistoricalWalkForwardValidationService,
    HistoricalWalkForwardValidationSummary,
    WalkForwardAggregateMetrics,
    WalkForwardFoldPlan,
    WalkForwardFoldResult,
)
from app.services.historical.historical_walkforward_validation import HistoricalWalkForwardValidationService as DirectService
from app.services.historical.historical_walkforward_validation_schemas import (
    HistoricalWalkForwardValidationConfig as DirectConfig,
)


def test_walkforward_validation_exports_are_available() -> None:
    assert HistoricalWalkForwardValidationService is DirectService
    assert HistoricalWalkForwardValidationConfig is DirectConfig
    assert HistoricalWalkForwardValidationSummary is not None
    assert WalkForwardAggregateMetrics is not None
    assert WalkForwardFoldPlan is not None
    assert WalkForwardFoldResult is not None


def test_walkforward_validation_defaults_match_phase_12h_foundation() -> None:
    config = HistoricalWalkForwardValidationConfig()

    assert config.validation_version_prefix == "12h_v1"
    assert config.split_mode == "anchored"
    assert config.label_key == "achieved_label"
