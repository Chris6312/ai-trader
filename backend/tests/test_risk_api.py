from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.trading import AssetClass, RiskEvent, RiskEventType, Signal, SignalStatus


def _build_test_sessionmaker():
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    return TestingSessionLocal


def test_recent_risk_rejections_endpoint_returns_structured_payload() -> None:
    testing_session_factory = _build_test_sessionmaker()

    with testing_session_factory() as db:
        db.add(
            RiskEvent(
                account_id=7,
                signal_id=11,
                event_type=RiskEventType.REJECTION,
                code="spread_too_wide",
                message=json.dumps(
                    {
                        "summary": "risk approval rejected",
                        "symbol": "AAPL",
                        "rejection_reason": "spread_too_wide",
                    }
                ),
                created_at=datetime.now(UTC),
            )
        )
        db.commit()

    def override_get_db():
        db = testing_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    response = client.get("/api/risk/rejections/recent")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["code"] == "spread_too_wide"
    assert payload[0]["payload"]["summary"] == "risk approval rejected"
    assert payload[0]["payload"]["symbol"] == "AAPL"


def test_signal_status_summary_endpoint_counts_signal_states() -> None:
    testing_session_factory = _build_test_sessionmaker()

    with testing_session_factory() as db:
        db.add_all(
            [
                Signal(
                    symbol="AAPL",
                    asset_class=AssetClass.STOCK,
                    strategy_name="momentum",
                    timeframe="1h",
                    confidence=0.81,
                    reasoning="{}",
                    status=SignalStatus.APPROVED,
                    created_at=datetime.now(UTC),
                ),
                Signal(
                    symbol="MSFT",
                    asset_class=AssetClass.STOCK,
                    strategy_name="trend_continuation",
                    timeframe="1h",
                    confidence=0.77,
                    reasoning="{}",
                    status=SignalStatus.REJECTED,
                    created_at=datetime.now(UTC),
                ),
                Signal(
                    symbol="BTC/USD",
                    asset_class=AssetClass.CRYPTO,
                    strategy_name="momentum",
                    timeframe="1h",
                    confidence=0.9,
                    reasoning="{}",
                    status=SignalStatus.NEW,
                    created_at=datetime.now(UTC),
                ),
            ]
        )
        db.commit()

    def override_get_db():
        db = testing_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    response = client.get("/api/risk/signals/status-summary")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    assert payload["approved"] == 1
    assert payload["rejected"] == 1
    assert payload["new"] == 1
    assert payload["executed"] == 0
    assert payload["approval_rate_percent"] == 33.33
    assert payload["rejection_rate_percent"] == 33.33