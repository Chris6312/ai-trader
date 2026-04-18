from __future__ import annotations

from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.services.historical.historical_backtesting_policy import HistoricalBacktestingPolicyService
from app.services.historical.historical_backtesting_policy_schemas import HistoricalBacktestingPolicy


def _build_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def test_historical_backtesting_policy_registers_policy_metadata() -> None:
    session = _build_session()
    service = HistoricalBacktestingPolicyService(session)

    record = service.register_policy()
    session.commit()

    assert record.policy_version == "12e_policy_v1"
    assert record.replay_policy_version == "12c_policy_v1"
    assert record.label_version == "12d_v1"
    assert record.evaluation_window_bars == 5
    assert record.regime_adjustments["risk_off"]["max_hold_bars"] == 4


def test_historical_backtesting_policy_registration_is_deterministic() -> None:
    session = _build_session()
    service = HistoricalBacktestingPolicyService(session)

    first = service.register_policy()
    session.commit()
    second = service.register_policy()
    session.commit()

    rows = service.list_policies()

    assert first.policy_version == second.policy_version
    assert len(rows) == 1


def test_historical_backtesting_policy_resolves_custom_policy() -> None:
    session = _build_session()
    service = HistoricalBacktestingPolicyService(
        session,
        policy=HistoricalBacktestingPolicy(
            policy_version="12e_policy_v2",
            policy_name="risk_off_tighter",
            replay_policy_version="12c_policy_v1",
            label_version="12d_v1",
            evaluation_window_bars=3,
            success_threshold_return=Decimal("0.015"),
            max_drawdown_return=Decimal("0.015"),
            require_target_before_stop=True,
            regime_adjustments={
                "risk_off": {
                    "success_threshold_multiplier": "1.50",
                    "max_hold_bars": 3,
                }
            },
        ),
    )
    service.register_policy()
    session.commit()

    resolved = service.resolve_policy("12e_policy_v2")

    assert resolved.policy_version == "12e_policy_v2"
    assert resolved.require_target_before_stop is True
    assert resolved.success_threshold_return == Decimal("0.015")
    assert resolved.regime_adjustments["risk_off"]["max_hold_bars"] == 3
