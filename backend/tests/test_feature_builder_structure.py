from __future__ import annotations

from app.services.historical import FeatureBuildSummary, FeatureBuilderService, HistoricalFeatureRecord
from app.services.historical.feature_builder import FeatureBuilderService as DirectFeatureBuilderService
from app.services.historical.feature_schemas import FeatureBuildSummary as DirectFeatureBuildSummary
from app.services.historical.feature_schemas import HistoricalFeatureRecord as DirectHistoricalFeatureRecord


def test_feature_builder_exports_are_available_from_package() -> None:
    assert FeatureBuilderService is DirectFeatureBuilderService
    assert HistoricalFeatureRecord is DirectHistoricalFeatureRecord
    assert FeatureBuildSummary is DirectFeatureBuildSummary


def test_feature_builder_uses_phase_11c_feature_version() -> None:
    service = FeatureBuilderService()

    assert service.FEATURE_VERSION == "11c_v1"
    assert service.warmup_period == 20
