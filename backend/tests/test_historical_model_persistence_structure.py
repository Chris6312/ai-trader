from __future__ import annotations

from app.services.historical import (
    HistoricalModelPersistenceConfig,
    HistoricalModelPersistenceService,
    HistoricalModelPersistenceSummary,
    ModelBundleVerificationSummary,
    PersistedModelReference,
)
from app.services.historical.historical_model_persistence import HistoricalModelPersistenceService as DirectService
from app.services.historical.historical_model_persistence_schemas import (
    HistoricalModelPersistenceConfig as DirectConfig,
)


def test_model_persistence_exports_are_available() -> None:
    assert HistoricalModelPersistenceService is DirectService
    assert HistoricalModelPersistenceConfig is DirectConfig
    assert HistoricalModelPersistenceSummary is not None
    assert ModelBundleVerificationSummary is not None
    assert PersistedModelReference is not None



def test_model_persistence_defaults_match_phase_12l_foundation() -> None:
    config = HistoricalModelPersistenceConfig()

    assert config.bundle_version_prefix == "12l_v1"
    assert config.bundle_name == "baseline_model_bundle"
    assert config.copy_model_artifact is True
