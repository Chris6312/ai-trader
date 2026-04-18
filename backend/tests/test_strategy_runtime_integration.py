from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.risk import OpenPositionSnapshot, RiskApprovalInput
from app.services import strategy_runtime_integration as sri


@dataclass
class DummyResult:
    strategy: str
    passed: bool


@dataclass
class DummySignal:
    id: int


@dataclass
class DummyRecord:
    result: DummyResult
    signal: DummySignal | None


class DummyEngine:
    def evaluate_symbol(self, db, bundle):
        return ["ok"]

    def evaluate_symbol_with_records(self, db, bundle):
        return [
            DummyRecord(result=DummyResult(strategy="momentum", passed=True), signal=DummySignal(id=101)),
            DummyRecord(result=DummyResult(strategy="trend_continuation", passed=False), signal=None),
        ]


class DummyRiskEngine:
    def evaluate_signal(self, db, signal, approval_input, account_id=None):
        return type(
            "ApprovalResult",
            (),
            {"approved": True, "rejection_reason": None},
        )()


class DummyDB:
    pass


class DummyBundle:
    pass


def _approval_input(symbol: str) -> RiskApprovalInput:
    return RiskApprovalInput(
        symbol=symbol,
        asset_class="crypto",
        account_equity=Decimal("10000"),
        proposed_notional_value=Decimal("500"),
        proposed_risk_amount=Decimal("50"),
        quote_bid=Decimal("99"),
        quote_ask=Decimal("100"),
        quote_age_seconds=5,
        open_positions=[OpenPositionSnapshot(symbol="ETH/USD", asset_class="crypto", notional_value=Decimal("250"))],
        max_open_positions=5,
        max_total_exposure_percent=Decimal("50"),
        max_symbol_exposure_percent=Decimal("25"),
        max_daily_loss_percent=Decimal("5"),
    )


def test_evaluate_from_candles_delegates_to_strategy_engine(monkeypatch):
    monkeypatch.setattr(sri, "engine", DummyEngine())

    result = sri.evaluate_from_candles(db=DummyDB(), bundle=DummyBundle())

    assert result == ["ok"]


def test_evaluate_from_candles_with_risk_applies_risk_to_persisted_signals(monkeypatch):
    monkeypatch.setattr(sri, "engine", DummyEngine())
    monkeypatch.setattr(sri, "risk_engine", DummyRiskEngine())

    result = sri.evaluate_from_candles_with_risk(
        db=DummyDB(),
        bundle=DummyBundle(),
        approval_inputs_by_strategy={"momentum": _approval_input("BTC/USD")},
        account_id=7,
    )

    assert len(result) == 2
    assert result[0].strategy == "momentum"
    assert result[0].signal_id == 101
    assert result[0].passed_strategy is True
    assert result[0].approved is True
    assert result[0].rejection_reason is None

    assert result[1].strategy == "trend_continuation"
    assert result[1].signal_id is None
    assert result[1].passed_strategy is False
    assert result[1].approved is None
