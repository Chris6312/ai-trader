from __future__ import annotations

from app.services.historical import (
    UniverseCandidateRecord,
    UniverseComposerService,
    UniverseCompositionSummary,
)
from app.services.historical.universe_composer import UniverseComposerService as DirectUniverseComposerService
from app.services.historical.universe_composer_schemas import UniverseCandidateRecord as DirectUniverseCandidateRecord
from app.services.historical.universe_composer_schemas import UniverseCompositionSummary as DirectUniverseCompositionSummary


def test_universe_composer_exports_are_available_from_package() -> None:
    assert UniverseComposerService is DirectUniverseComposerService
    assert UniverseCandidateRecord is DirectUniverseCandidateRecord
    assert UniverseCompositionSummary is DirectUniverseCompositionSummary


def test_universe_composer_uses_phase_11g_composition_version() -> None:
    service = UniverseComposerService()

    assert service.COMPOSITION_VERSION == "11g_v1"
    assert service.SUPPORTED_TECHNICAL_SCORING_VERSIONS == {"11d_v1"}
    assert service.SUPPORTED_SENTIMENT_SCORING_VERSIONS == {"11e_v1"}
    assert service.SUPPORTED_REGIME_DETECTION_VERSIONS == {"11f_v1"}
