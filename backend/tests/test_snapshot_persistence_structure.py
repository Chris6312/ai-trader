from __future__ import annotations

from app.models.ai_research import RegimeSnapshot, SentimentSnapshot, TechnicalSnapshot, UniverseSnapshot
from app.services.historical import AISnapshotPersistenceService, SnapshotPersistenceSummary


def test_snapshot_models_and_exports_are_available() -> None:
    assert TechnicalSnapshot.__tablename__ == "ai_technical_snapshots"
    assert SentimentSnapshot.__tablename__ == "ai_sentiment_snapshots"
    assert RegimeSnapshot.__tablename__ == "ai_regime_snapshots"
    assert UniverseSnapshot.__tablename__ == "ai_universe_snapshots"
    assert AISnapshotPersistenceService is not None
    assert SnapshotPersistenceSummary is not None
