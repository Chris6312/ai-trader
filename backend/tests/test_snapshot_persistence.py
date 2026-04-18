from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.ai_research import RegimeSnapshot, SentimentSnapshot, TechnicalSnapshot, UniverseSnapshot
from app.services.historical.regime_detection_schemas import RegimeDetectionRecord
from app.services.historical.sentiment_scoring_schemas import SentimentScoreRecord
from app.services.historical.snapshot_persistence import AISnapshotPersistenceService
from app.services.historical.technical_scoring_schemas import TechnicalScoreRecord
from app.services.historical.universe_composer_schemas import UniverseCandidateRecord


def _build_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def test_persist_technical_scores_inserts_and_replaces_rows() -> None:
    session = _build_session()
    service = AISnapshotPersistenceService(session)
    candle_time = datetime(2026, 4, 18, 12, 0, tzinfo=UTC)

    first = TechnicalScoreRecord(
        symbol="AAPL",
        asset_class="stock",
        timeframe="1d",
        candle_time=candle_time,
        source_label="alpaca",
        feature_version="feature_v1",
        scoring_version="technical_v1",
        technical_score=Decimal("0.61"),
        component_scores={"trend": Decimal("0.70")},
        inputs={"close": Decimal("101.25")},
    )
    summary_one = service.persist_technical_scores([first])
    session.commit()

    assert summary_one.rows_inserted == 1
    assert summary_one.rows_replaced == 0

    replacement = TechnicalScoreRecord(
        symbol="AAPL",
        asset_class="stock",
        timeframe="1d",
        candle_time=candle_time,
        source_label="alpaca",
        feature_version="feature_v1",
        scoring_version="technical_v2",
        technical_score=Decimal("0.72"),
        component_scores={"trend": Decimal("0.80")},
        inputs={"close": Decimal("102.00")},
    )
    summary_two = service.persist_technical_scores([replacement])
    session.commit()

    assert summary_two.rows_inserted == 1
    assert summary_two.rows_replaced == 1

    row = session.scalar(select(TechnicalSnapshot))
    assert row is not None
    assert row.scoring_version == "technical_v2"
    assert row.component_scores_json == {"trend": "0.80"}
    assert row.inputs_json == {"close": "102.00"}


def test_persist_sentiment_scores_serializes_decimal_payloads() -> None:
    session = _build_session()
    service = AISnapshotPersistenceService(session)

    summary = service.persist_sentiment_scores(
        [
            SentimentScoreRecord(
                symbol="BTC/USD",
                asset_class="crypto",
                timeframe="4h",
                candle_time=datetime(2026, 4, 18, 8, 0, tzinfo=UTC),
                source_label="kraken_csv",
                input_version="sentiment_input_v1",
                scoring_version="sentiment_v1",
                sentiment_score=Decimal("0.55"),
                component_scores={"macro_alignment": Decimal("0.65")},
                inputs={"macro_alignment": Decimal("0.65")},
            )
        ]
    )
    session.commit()

    assert summary.rows_inserted == 1
    row = session.scalar(select(SentimentSnapshot))
    assert row is not None
    assert row.component_scores_json == {"macro_alignment": "0.65"}
    assert row.inputs_json == {"macro_alignment": "0.65"}


def test_persist_regime_and_universe_snapshots() -> None:
    session = _build_session()
    service = AISnapshotPersistenceService(session)
    candle_time = datetime(2026, 4, 18, 0, 0, tzinfo=UTC)

    regime_summary = service.persist_regime_detections(
        [
            RegimeDetectionRecord(
                symbol="ETH/USD",
                asset_class="crypto",
                timeframe="1d",
                candle_time=candle_time,
                source_label="kraken_csv",
                technical_scoring_version="technical_v1",
                sentiment_scoring_version="sentiment_v1",
                detection_version="regime_v1",
                regime_label="risk_on",
                regime_score=Decimal("0.77"),
                component_scores={"blend": Decimal("0.77")},
                inputs={"technical_score": Decimal("0.81")},
            )
        ]
    )
    universe_summary = service.persist_universe_candidates(
        [
            UniverseCandidateRecord(
                symbol="ETH/USD",
                asset_class="crypto",
                timeframe="1d",
                candle_time=candle_time,
                source_label="kraken_csv",
                technical_scoring_version="technical_v1",
                sentiment_scoring_version="sentiment_v1",
                regime_detection_version="regime_v1",
                composition_version="universe_v1",
                rank=1,
                selected=True,
                universe_score=Decimal("0.84"),
                decision_label="include",
                component_scores={"total": Decimal("0.84")},
                inputs={"regime_score": Decimal("0.77")},
            )
        ]
    )
    session.commit()

    assert regime_summary.rows_inserted == 1
    assert universe_summary.rows_inserted == 1
    assert session.scalar(select(RegimeSnapshot)) is not None
    assert session.scalar(select(UniverseSnapshot)) is not None
