from __future__ import annotations

from app.services.historical import (
    FeatureDriftRecord,
    FeatureImportanceFoldReview,
    FeatureImportanceRecord,
    HistoricalFeatureImportanceReviewConfig,
    HistoricalFeatureImportanceReviewService,
    HistoricalFeatureImportanceReviewSummary,
)
from app.services.historical.historical_feature_importance_review import HistoricalFeatureImportanceReviewService as DirectService
from app.services.historical.historical_feature_importance_review_schemas import (
    HistoricalFeatureImportanceReviewConfig as DirectConfig,
)


def test_feature_importance_review_exports_are_available() -> None:
    assert HistoricalFeatureImportanceReviewService is DirectService
    assert HistoricalFeatureImportanceReviewConfig is DirectConfig
    assert HistoricalFeatureImportanceReviewSummary is not None
    assert FeatureImportanceRecord is not None
    assert FeatureDriftRecord is not None
    assert FeatureImportanceFoldReview is not None


def test_feature_importance_review_defaults_match_phase_12i_foundation() -> None:
    config = HistoricalFeatureImportanceReviewConfig()

    assert config.report_version_prefix == "12i_v1"
    assert config.validation_config.validation_version_prefix == "12h_v1"
    assert config.drift_psi_threshold == 0.2
