from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import AssetClass
from app.models.ai_research import (
    BacktestingPolicyVersion,
    FeatureDefinitionVersion,
    HistoricalFeatureRow,
    HistoricalReplayLabel,
    HistoricalStrategyReplay,
    HistoricalUniverseSnapshot,
)
from app.services.historical.historical_training_dataset import HistoricalTrainingDatasetService


def _build_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed_common_rows(session: Session, *, decision_date, entry_time: datetime) -> None:
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
            source_label="phase12a_test",
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
    session.add_all(
        [
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
            HistoricalFeatureRow(
                decision_date=decision_date,
                symbol="AAPL",
                asset_class=AssetClass.STOCK,
                timeframe="1h",
                candle_time=entry_time.replace(hour=13),
                source_label="alpaca",
                feature_version="11c_v1",
                values_json={"close_vs_sma_20": "0.999", "volume_ratio_5": "9.99"},
            ),
        ]
    )
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
    session.flush()


def test_training_dataset_builds_point_in_time_rows_without_future_leakage() -> None:
    session = _build_session()
    entry_time = datetime(2026, 4, 18, 12, 0, tzinfo=UTC)
    _seed_common_rows(session, decision_date=entry_time.date(), entry_time=entry_time)
    service = HistoricalTrainingDatasetService(session)

    summary = service.build_dataset(
        start_date=entry_time.date(),
        end_date=entry_time.date(),
        asset_class=AssetClass.STOCK,
        timeframe="1h",
        policy_version="12e_policy_v1",
        feature_version="11c_v1",
        source_label="alpaca",
        strategy_name="momentum",
    )
    session.commit()

    rows = service.list_dataset_rows(summary.dataset_version)
    assert summary.rows_considered == 1
    assert summary.rows_built == 1
    assert rows[0].feature_values["close_vs_sma_20"] == "0.025"
    assert rows[0].feature_values["volume_ratio_5"] == "1.40"
    assert rows[0].metadata["feature_candle_time"].endswith("11:00:00+00:00")
    assert rows[0].label_values["achieved_label"] is True


def test_training_dataset_build_is_deterministic_for_same_scope() -> None:
    session = _build_session()
    entry_time = datetime(2026, 4, 18, 12, 0, tzinfo=UTC)
    _seed_common_rows(session, decision_date=entry_time.date(), entry_time=entry_time)
    service = HistoricalTrainingDatasetService(session)

    first = service.build_dataset(
        start_date=entry_time.date(),
        end_date=entry_time.date(),
        asset_class=AssetClass.STOCK,
        timeframe="1h",
        policy_version="12e_policy_v1",
        feature_version="11c_v1",
        source_label="alpaca",
        strategy_name="momentum",
    )
    session.commit()

    second = service.build_dataset(
        start_date=entry_time.date(),
        end_date=entry_time.date(),
        asset_class=AssetClass.STOCK,
        timeframe="1h",
        policy_version="12e_policy_v1",
        feature_version="11c_v1",
        source_label="alpaca",
        strategy_name="momentum",
    )
    session.commit()

    rows = service.list_dataset_rows(first.dataset_version)
    versions = service.list_dataset_versions()

    assert first.dataset_version == second.dataset_version
    assert second.rows_replaced == 1
    assert len(rows) == 1
    assert len(versions) == 1
    assert versions[0].row_count == 1
    assert versions[0].build_metadata["rows_considered"] == 1


def test_training_dataset_skips_rows_missing_label_or_universe() -> None:
    session = _build_session()
    entry_time = datetime(2026, 4, 18, 12, 0, tzinfo=UTC)
    _seed_common_rows(session, decision_date=entry_time.date(), entry_time=entry_time)
    session.add(
        HistoricalStrategyReplay(
            decision_date=entry_time.date(),
            symbol="MSFT",
            asset_class=AssetClass.STOCK,
            timeframe="1h",
            strategy_name="momentum",
            source_label="alpaca",
            replay_version="12c_v1",
            policy_version="12e_policy_v1",
            entry_candle_time=entry_time.replace(hour=12),
            exit_candle_time=entry_time.replace(hour=13),
            entry_price=Decimal("200"),
            exit_price=Decimal("201"),
            stop_price=Decimal("196"),
            target_price=Decimal("208"),
            entry_confidence=Decimal("0.71"),
            risk_approved=True,
            exit_reason="time_expired",
            hold_bars=1,
            max_favorable_excursion=Decimal("0.01"),
            max_adverse_excursion=Decimal("-0.01"),
            gross_return=Decimal("0.005"),
            strategy_summary="no label",
            strategy_checks_json={"passed": True},
            strategy_indicators_json={"rvol": "1.2"},
            risk_rejection_reason=None,
        )
    )
    session.flush()

    service = HistoricalTrainingDatasetService(session)
    summary = service.build_dataset(
        start_date=entry_time.date(),
        end_date=entry_time.date(),
        asset_class=AssetClass.STOCK,
        timeframe="1h",
        policy_version="12e_policy_v1",
        feature_version="11c_v1",
        source_label="alpaca",
        strategy_name="momentum",
    )
    session.commit()

    assert summary.rows_considered == 2
    assert summary.rows_built == 1
    assert summary.rows_skipped_missing_universe == 1
    assert summary.rows_skipped_missing_label == 0
