from __future__ import annotations

from app.services.historical import (
    RegimeDetectionRecord,
    RegimeDetectionService,
    RegimeDetectionSummary,
)
from app.services.historical.regime_detection import RegimeDetectionService as DirectRegimeDetectionService
from app.services.historical.regime_detection_schemas import RegimeDetectionRecord as DirectRegimeDetectionRecord
from app.services.historical.regime_detection_schemas import RegimeDetectionSummary as DirectRegimeDetectionSummary


def test_regime_detection_exports_are_available_from_package() -> None:
    assert RegimeDetectionService is DirectRegimeDetectionService
    assert RegimeDetectionRecord is DirectRegimeDetectionRecord
    assert RegimeDetectionSummary is DirectRegimeDetectionSummary


def test_regime_detection_uses_phase_11f_detection_version() -> None:
    service = RegimeDetectionService()

    assert service.DETECTION_VERSION == "11f_v1"
    assert service.SUPPORTED_TECHNICAL_SCORING_VERSIONS == {"11d_v1"}
    assert service.SUPPORTED_SENTIMENT_SCORING_VERSIONS == {"11e_v1"}
