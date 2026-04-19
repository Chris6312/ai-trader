from __future__ import annotations

from app.models import FeatureDefinitionVersion, HistoricalFeatureRow
from app.services.historical import (
    FeatureDefinitionVersionRecord,
    HistoricalFeatureStoreBuildSummary,
    HistoricalFeatureStoreRowRecord,
    HistoricalFeatureStoreService,
)
from app.services.historical.feature_store_schemas import (
    FeatureDefinitionVersionRecord as DirectFeatureDefinitionVersionRecord,
)
from app.services.historical.feature_store_schemas import (
    HistoricalFeatureStoreBuildSummary as DirectHistoricalFeatureStoreBuildSummary,
)
from app.services.historical.feature_store_schemas import (
    HistoricalFeatureStoreRowRecord as DirectHistoricalFeatureStoreRowRecord,
)
from app.services.historical.historical_feature_store import HistoricalFeatureStoreService as DirectHistoricalFeatureStoreService


def test_historical_feature_store_exports_are_available_from_package() -> None:
    assert HistoricalFeatureStoreService is DirectHistoricalFeatureStoreService
    assert FeatureDefinitionVersionRecord is DirectFeatureDefinitionVersionRecord
    assert HistoricalFeatureStoreRowRecord is DirectHistoricalFeatureStoreRowRecord
    assert HistoricalFeatureStoreBuildSummary is DirectHistoricalFeatureStoreBuildSummary


def test_historical_feature_store_models_are_exported() -> None:
    assert FeatureDefinitionVersion.__tablename__ == "feature_definition_versions"
    assert HistoricalFeatureRow.__tablename__ == "historical_feature_rows"
