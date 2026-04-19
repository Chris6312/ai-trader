from __future__ import annotations

from app.services.historical import (
    HistoricalMLScoringConfig,
    HistoricalMLScoringService,
    HistoricalMLScoringSummary,
    MLScoreExplanationRecord,
    MLScoredCandidateRecord,
    MLScoringCandidateInput,
)
from app.services.historical.historical_ml_scoring import HistoricalMLScoringService as DirectService
from app.services.historical.historical_ml_scoring_schemas import HistoricalMLScoringConfig as DirectConfig


def test_ml_scoring_exports_are_available() -> None:
    assert HistoricalMLScoringService is DirectService
    assert HistoricalMLScoringConfig is DirectConfig
    assert HistoricalMLScoringSummary is not None
    assert MLScoringCandidateInput is not None
    assert MLScoredCandidateRecord is not None
    assert MLScoreExplanationRecord is not None


def test_ml_scoring_defaults_match_phase_12j_foundation() -> None:
    config = HistoricalMLScoringConfig()

    assert config.scoring_version_prefix == "12j_v1"
    assert config.base_score_weight == 0.65
    assert config.ml_score_weight == 0.35
