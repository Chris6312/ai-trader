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
from app.models import AssetClass
from app.models.ai_research import (
    BacktestingPolicyVersion,
    FeatureDefinitionVersion,
    HistoricalFeatureRow,
    HistoricalReplayLabel,
    HistoricalStrategyReplay,
    HistoricalUniverseSnapshot,
)


class FakeRedis:
    def __init__(self) -> None:
        self.storage: dict[str, str] = {}

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.storage[key] = value

    def get(self, key: str) -> str | None:
        return self.storage.get(key)


def _seed_dataset_prereqs(session: Session) -> None:
    entry_time = datetime(2026, 4, 18, 12, 0, tzinfo=UTC)
    decision_date = entry_time.date()
    session.add(
        FeatureDefinitionVersion(
            feature_version="11c_v1",
            warmup_period=20,
            feature_keys_json=["close_vs_sma_20", "volume_ratio_5"],
        )
    )
    session.add(
        BacktestingPolicyVersion(
            policy_version="12e_policy_v1",
            policy_name="baseline_backtest",
            replay_policy_version="12c_v1",
            label_version="12d_v1",
            evaluation_window_bars=5,
            success_threshold_return=Decimal("0.01"),
            max_drawdown_return=Decimal("0.02"),
            require_target_before_stop=False,
            regime_adjustments_json={"risk_off": {"max_hold_bars": 4}},
        )
    )
    session.add(
        HistoricalUniverseSnapshot(
            decision_date=decision_date,
            symbol="AAPL",
            asset_class=AssetClass.STOCK,
            source_label="alpaca",
            registry_source="sp500",
            is_active=True,
            is_tradable=True,
            history_status="ready",
            sector_or_category="Technology",
            avg_dollar_volume=Decimal("1000000.00"),
            first_seen_at=entry_time,
            last_seen_at=entry_time,
            metadata_json={"provider_symbol": "AAPL"},
        )
    )
    session.add_all([
        HistoricalFeatureRow(
            decision_date=decision_date,
            symbol="AAPL",
            asset_class=AssetClass.STOCK,
            timeframe="1h",
            candle_time=entry_time.replace(hour=10),
            source_label="alpaca",
            feature_version="11c_v1",
            values_json={"close_vs_sma_20": "0.015", "volume_ratio_5": "1.20"},
        ),
        HistoricalFeatureRow(
            decision_date=decision_date,
            symbol="AAPL",
            asset_class=AssetClass.STOCK,
            timeframe="1h",
            candle_time=entry_time.replace(hour=11),
            source_label="alpaca",
            feature_version="11c_v1",
            values_json={"close_vs_sma_20": "0.025", "volume_ratio_5": "1.40"},
        ),
    ])
    session.add(
        HistoricalStrategyReplay(
            decision_date=decision_date,
            symbol="AAPL",
            asset_class=AssetClass.STOCK,
            timeframe="1h",
            strategy_name="momentum",
            source_label="alpaca",
            replay_version="12c_v1",
            policy_version="12e_policy_v1",
            entry_candle_time=entry_time.replace(hour=12),
            exit_candle_time=entry_time.replace(hour=14),
            entry_price=Decimal("100"),
            exit_price=Decimal("103"),
            stop_price=Decimal("98"),
            target_price=Decimal("104"),
            entry_confidence=Decimal("0.80"),
            risk_approved=True,
            exit_reason="target_hit",
            hold_bars=2,
            max_favorable_excursion=Decimal("0.05"),
            max_adverse_excursion=Decimal("-0.01"),
            gross_return=Decimal("0.03"),
            strategy_summary="clean breakout",
            strategy_checks_json={"passed": True},
            strategy_indicators_json={"rvol": "1.8"},
            risk_rejection_reason=None,
        )
    )
    session.add(
        HistoricalReplayLabel(
            decision_date=decision_date,
            symbol="AAPL",
            asset_class=AssetClass.STOCK,
            timeframe="1h",
            strategy_name="momentum",
            entry_candle_time=entry_time.replace(hour=12),
            source_label="alpaca",
            replay_version="12c_v1",
            label_version="12d_v1",
            is_trade_profitable=True,
            hit_target_before_stop=True,
            follow_through_strength=Decimal("0.80"),
            drawdown_within_limit=True,
            achieved_label=True,
            label_values_json={"achieved_label": True, "follow_through_strength": "0.80"},
        )
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
    _seed_dataset_prereqs(session)
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
            yield client, TestingSessionLocal
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_ml_dataset_build_creates_dataset_from_latest_matching_replays(monkeypatch) -> None:
    with _test_client(monkeypatch) as payload:
        client, _ = payload
        response = client.post(
            "/api/ai/ml/datasets/build",
            json={"asset_class": "stock", "timeframe": "1h", "source_label": "alpaca", "strategy_name": "momentum"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["rows_built"] == 1
    assert payload["strategy_name"] == "momentum"
    assert payload["source_label"] == "alpaca"
    assert payload["start_date"] == "2026-04-18"
    assert payload["end_date"] == "2026-04-18"


def test_ml_dataset_build_returns_404_when_no_matching_replays_exist(monkeypatch) -> None:
    with _test_client(monkeypatch) as payload:
        client, _ = payload
        response = client.post(
            "/api/ai/ml/datasets/build",
            json={"asset_class": "stock", "timeframe": "1d", "source_label": "alpaca", "strategy_name": "momentum"},
        )

    assert response.status_code == 404
    assert "no matching historical replay rows" in response.json()["detail"]


def test_ml_dataset_build_filters_by_source_label(monkeypatch) -> None:
    with _test_client(monkeypatch) as payload:
        client, testing_session_local = payload
        with testing_session_local() as session:
            entry_time = datetime(2026, 4, 18, 13, 0, tzinfo=UTC)
            decision_date = entry_time.date()
            session.add(
                HistoricalStrategyReplay(
                    decision_date=decision_date,
                    symbol="AAPL",
                    asset_class=AssetClass.STOCK,
                    timeframe="1h",
                    strategy_name="momentum",
                    source_label="yfinance",
                    replay_version="12c_v1",
                    policy_version="12e_policy_v1",
                    entry_candle_time=entry_time,
                    exit_candle_time=entry_time.replace(hour=14),
                    entry_price=Decimal("100"),
                    exit_price=Decimal("102"),
                    stop_price=Decimal("98"),
                    target_price=Decimal("104"),
                    entry_confidence=Decimal("0.70"),
                    risk_approved=True,
                    exit_reason="target_hit",
                    hold_bars=1,
                    max_favorable_excursion=Decimal("0.02"),
                    max_adverse_excursion=Decimal("-0.01"),
                    gross_return=Decimal("0.02"),
                    strategy_summary="alternate provider replay",
                    strategy_checks_json={"passed": True},
                    strategy_indicators_json={"rvol": "1.2"},
                    risk_rejection_reason=None,
                )
            )
            session.commit()

        response = client.post(
            "/api/ai/ml/datasets/build",
            json={"asset_class": "stock", "timeframe": "1h", "source_label": "yfinance", "strategy_name": "momentum"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["rows_built"] == 0
    assert payload["rows_skipped_missing_label"] == 1
    assert payload["source_label"] == "yfinance"
    assert payload["start_date"] == "2026-04-18"
    assert payload["end_date"] == "2026-04-18"
