from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import AssetClass
from app.models.ai_research import HistoricalStrategyReplay
from app.services.historical.historical_label_generator import HistoricalLabelGeneratorService
from app.services.historical.historical_label_schemas import HistoricalLabelPolicy


def _build_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed_replay_rows(session: Session, *, seen_at: datetime) -> None:
    session.add_all(
        [
            HistoricalStrategyReplay(
                decision_date=seen_at.date(),
                symbol="AAPL",
                asset_class=AssetClass.STOCK,
                timeframe="1h",
                strategy_name="momentum",
                source_label="alpaca",
                replay_version="12c_v1",
                policy_version="12c_policy_v1",
                entry_candle_time=seen_at,
                exit_candle_time=seen_at,
                entry_price=Decimal("100"),
                exit_price=Decimal("103"),
                stop_price=Decimal("98"),
                target_price=Decimal("104"),
                entry_confidence=Decimal("0.80"),
                risk_approved=True,
                exit_reason="target_hit",
                hold_bars=2,
                max_favorable_excursion=Decimal("0.05000000"),
                max_adverse_excursion=Decimal("-0.01000000"),
                gross_return=Decimal("0.03000000"),
                strategy_summary="clean breakout",
                strategy_checks_json={"passed": True},
                strategy_indicators_json={"rvol": "1.8"},
                risk_rejection_reason=None,
            ),
            HistoricalStrategyReplay(
                decision_date=seen_at.date(),
                symbol="MSFT",
                asset_class=AssetClass.STOCK,
                timeframe="1h",
                strategy_name="momentum",
                source_label="alpaca",
                replay_version="12c_v1",
                policy_version="12c_policy_v1",
                entry_candle_time=seen_at.replace(hour=13),
                exit_candle_time=seen_at.replace(hour=15),
                entry_price=Decimal("200"),
                exit_price=Decimal("198"),
                stop_price=Decimal("196"),
                target_price=Decimal("208"),
                entry_confidence=Decimal("0.70"),
                risk_approved=True,
                exit_reason="time_expired",
                hold_bars=5,
                max_favorable_excursion=Decimal("0.00800000"),
                max_adverse_excursion=Decimal("-0.03000000"),
                gross_return=Decimal("-0.01000000"),
                strategy_summary="failed follow through",
                strategy_checks_json={"passed": True},
                strategy_indicators_json={"rvol": "0.9"},
                risk_rejection_reason=None,
            ),
            HistoricalStrategyReplay(
                decision_date=seen_at.date(),
                symbol="NVDA",
                asset_class=AssetClass.STOCK,
                timeframe="1h",
                strategy_name="momentum",
                source_label="alpaca",
                replay_version="12c_v1",
                policy_version="12c_policy_v1",
                entry_candle_time=seen_at.replace(hour=16),
                exit_candle_time=seen_at.replace(hour=17),
                entry_price=Decimal("300"),
                exit_price=Decimal("300"),
                stop_price=Decimal("294"),
                target_price=Decimal("312"),
                entry_confidence=Decimal("0.60"),
                risk_approved=False,
                exit_reason="risk_rejected",
                hold_bars=0,
                max_favorable_excursion=Decimal("0.00000000"),
                max_adverse_excursion=Decimal("0.00000000"),
                gross_return=Decimal("0.00000000"),
                strategy_summary="blocked by risk",
                strategy_checks_json={"passed": True},
                strategy_indicators_json={"rvol": "1.1"},
                risk_rejection_reason="max_positions",
            ),
        ]
    )
    session.flush()


def test_historical_label_generator_builds_labels_from_approved_replays_only() -> None:
    session = _build_session()
    seen_at = datetime(2026, 4, 18, 12, 0, tzinfo=UTC)
    _seed_replay_rows(session, seen_at=seen_at)
    service = HistoricalLabelGeneratorService(
        session,
        policy=HistoricalLabelPolicy(
            label_version="12d_v1",
            policy_name="baseline_replay_success",
            success_threshold_return=Decimal("0.01"),
            max_drawdown_return=Decimal("0.02"),
            require_target_before_stop=False,
            max_hold_bars=5,
        ),
    )

    summary = service.build_for_decision_date(
        decision_date=seen_at.date(),
        asset_class=AssetClass.STOCK,
        timeframe="1h",
    )
    session.commit()

    rows = service.list_rows(
        decision_date=seen_at.date(),
        asset_class=AssetClass.STOCK,
        timeframe="1h",
    )

    assert summary.rows_considered == 2
    assert summary.rows_labeled == 2
    assert [row.symbol for row in rows] == ["AAPL", "MSFT"]
    assert rows[0].achieved_label is True
    assert rows[0].hit_target_before_stop is True
    assert rows[1].achieved_label is False
    assert rows[1].drawdown_within_limit is False


def test_historical_label_generator_replaces_existing_labels_deterministically() -> None:
    session = _build_session()
    seen_at = datetime(2026, 4, 18, 12, 0, tzinfo=UTC)
    _seed_replay_rows(session, seen_at=seen_at)
    service = HistoricalLabelGeneratorService(session)

    first = service.build_for_decision_date(
        decision_date=seen_at.date(),
        asset_class=AssetClass.STOCK,
        timeframe="1h",
    )
    session.commit()

    second = service.build_for_decision_date(
        decision_date=seen_at.date(),
        asset_class=AssetClass.STOCK,
        timeframe="1h",
    )
    session.commit()

    rows = service.list_rows(
        decision_date=seen_at.date(),
        asset_class=AssetClass.STOCK,
        timeframe="1h",
    )

    assert first.rows_labeled == 2
    assert second.rows_replaced == 2
    assert len(rows) == 2


def test_historical_label_generator_registers_label_policy_metadata() -> None:
    session = _build_session()
    service = HistoricalLabelGeneratorService(session)

    record = service.register_label_policy()
    session.commit()

    assert record.label_version == "12d_v1"
    assert record.policy_name == "baseline_replay_success"
    assert record.max_hold_bars == 5
