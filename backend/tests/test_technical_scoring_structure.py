from __future__ import annotations

from app.services.historical import TechnicalScoreRecord, TechnicalScoreSummary, TechnicalScoringService
from app.services.historical.technical_scoring import TechnicalScoringService as DirectTechnicalScoringService
from app.services.historical.technical_scoring_schemas import TechnicalScoreRecord as DirectTechnicalScoreRecord
from app.services.historical.technical_scoring_schemas import TechnicalScoreSummary as DirectTechnicalScoreSummary


def test_technical_scoring_exports_are_available_from_package() -> None:
    assert TechnicalScoringService is DirectTechnicalScoringService
    assert TechnicalScoreRecord is DirectTechnicalScoreRecord
    assert TechnicalScoreSummary is DirectTechnicalScoreSummary


def test_technical_scoring_uses_phase_11d_scoring_version() -> None:
    service = TechnicalScoringService()

    assert service.SCORING_VERSION == "11d_v1"
    assert service.SUPPORTED_FEATURE_VERSIONS == {"11c_v1"}
