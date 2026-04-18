from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from redis import Redis
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.main import app
from app.models.ai_research import RegimeSnapshot, SentimentSnapshot, TechnicalSnapshot, UniverseSnapshot


class FakeRedis:
    def __init__(self) -> None:
        self.storage: dict[str, str] = {}

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.storage[key] = value

    def get(self, key: str) -> str | None:
        return self.storage.get(key)


def _seed_snapshot_rows(session: Session) -> None:
    candle_time = datetime(2026, 4, 18, 12, 0, tzinfo=UTC)
    older_candle_time = datetime(2026, 4, 17, 12, 0, tzinfo=UTC)

    session.add_all(
        [
            TechnicalSnapshot(
                symbol="AAPL",
                asset_class="stock",
                timeframe="1d",
                candle_time=older_candle_time,
                source_label="alpaca",
                feature_version="feature_v1",
                scoring_version="technical_v1",
                technical_score=Decimal("0.51"),
                component_scores_json={"trend": "0.51"},
                inputs_json={"close": "100.00"},
            ),
            TechnicalSnapshot(
                symbol="AAPL",
                asset_class="stock",
                timeframe="1d",
                candle_time=candle_time,
                source_label="alpaca",
                feature_version="feature_v1",
                scoring_version="technical_v2",
                technical_score=Decimal("0.82"),
                component_scores_json={"trend": "0.84"},
                inputs_json={"close": "105.25"},
            ),
            SentimentSnapshot(
                symbol="AAPL",
                asset_class="stock",
                timeframe="1d",
                candle_time=candle_time,
                source_label="alpaca",
                input_version="sentiment_input_v1",
                scoring_version="sentiment_v1",
                sentiment_score=Decimal("0.67"),
                component_scores_json={"macro": "0.62"},
                inputs_json={"headline_count": 4},
            ),
            RegimeSnapshot(
                symbol="AAPL",
                asset_class="stock",
                timeframe="1d",
                candle_time=candle_time,
                source_label="alpaca",
                technical_scoring_version="technical_v2",
                sentiment_scoring_version="sentiment_v1",
                detection_version="regime_v1",
                regime_label="risk_on",
                regime_score=Decimal("0.76"),
                component_scores_json={"stability": "0.70"},
                inputs_json={"technical_score": "0.82"},
            ),
            UniverseSnapshot(
                symbol="AAPL",
                asset_class="stock",
                timeframe="1d",
                candle_time=candle_time,
                source_label="alpaca",
                technical_scoring_version="technical_v2",
                sentiment_scoring_version="sentiment_v1",
                regime_detection_version="regime_v1",
                composition_version="universe_v1",
                rank=1,
                selected=True,
                universe_score=Decimal("0.88"),
                decision_label="include",
                component_scores_json={"conviction": "0.83"},
                inputs_json={"regime_score": "0.76"},
            ),
            UniverseSnapshot(
                symbol="MSFT",
                asset_class="stock",
                timeframe="1d",
                candle_time=candle_time,
                source_label="alpaca",
                technical_scoring_version="technical_v2",
                sentiment_scoring_version="sentiment_v1",
                regime_detection_version="regime_v1",
                composition_version="universe_v1",
                rank=2,
                selected=False,
                universe_score=Decimal("0.59"),
                decision_label="watch",
                component_scores_json={"conviction": "0.58"},
                inputs_json={"regime_score": "0.60"},
            ),
        ]
    )
    session.commit()


@contextmanager
def _test_client(monkeypatch):
    monkeypatch.setattr(Redis, "from_url", lambda *args, **kwargs: FakeRedis())

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    session = TestingSessionLocal()
    _seed_snapshot_rows(session)
    session.close()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    from app.db.session import get_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_latest_snapshot_bundle_returns_aligned_research_rows(monkeypatch) -> None:
    with _test_client(monkeypatch) as client:
        response = client.get(
            "/api/ai/snapshots/latest",
            params={"symbol": "AAPL", "asset_class": "stock", "timeframe": "1d"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["filters"]["symbol"] == "AAPL"
    assert payload["filters"]["source_label"] == "alpaca"
    assert payload["technical"]["scoring_version"] == "technical_v2"
    assert payload["sentiment"]["scoring_version"] == "sentiment_v1"
    assert payload["regime"]["regime_label"] == "risk_on"
    assert len(payload["universe_candidates"]) == 1
    assert payload["universe_candidates"][0]["rank"] == 1


def test_latest_snapshot_bundle_returns_404_when_missing(monkeypatch) -> None:
    with _test_client(monkeypatch) as client:
        response = client.get(
            "/api/ai/snapshots/latest",
            params={"symbol": "NVDA", "asset_class": "stock", "timeframe": "1d"},
        )

    assert response.status_code == 404


def test_latest_universe_endpoint_defaults_to_selected_rows(monkeypatch) -> None:
    with _test_client(monkeypatch) as client:
        response = client.get("/api/ai/universe/latest", params={"asset_class": "stock", "timeframe": "1d"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["returned"] == 1
    assert payload["selected_only"] is True
    assert payload["rows"][0]["symbol"] == "AAPL"


def test_latest_universe_endpoint_can_include_watch_rows(monkeypatch) -> None:
    with _test_client(monkeypatch) as client:
        response = client.get(
            "/api/ai/universe/latest",
            params={"asset_class": "stock", "timeframe": "1d", "selected_only": "false", "limit": 5},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["returned"] == 2
    assert [row["symbol"] for row in payload["rows"]] == ["AAPL", "MSFT"]
