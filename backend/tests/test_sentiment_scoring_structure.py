from __future__ import annotations

from app.services.historical import (
    SentimentInputRecord,
    SentimentScoreRecord,
    SentimentScoreSummary,
    SentimentScoringService,
)
from app.services.historical.sentiment_scoring import SentimentScoringService as DirectSentimentScoringService
from app.services.historical.sentiment_scoring_schemas import SentimentInputRecord as DirectSentimentInputRecord
from app.services.historical.sentiment_scoring_schemas import SentimentScoreRecord as DirectSentimentScoreRecord
from app.services.historical.sentiment_scoring_schemas import SentimentScoreSummary as DirectSentimentScoreSummary


def test_sentiment_scoring_exports_are_available_from_package() -> None:
    assert SentimentScoringService is DirectSentimentScoringService
    assert SentimentInputRecord is DirectSentimentInputRecord
    assert SentimentScoreRecord is DirectSentimentScoreRecord
    assert SentimentScoreSummary is DirectSentimentScoreSummary


def test_sentiment_scoring_uses_phase_11e_scoring_version() -> None:
    service = SentimentScoringService()

    assert service.SCORING_VERSION == "11e_v1"
    assert service.SUPPORTED_INPUT_VERSIONS == {"11e_input_v1"}
