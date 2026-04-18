from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.risk import OpenPositionSnapshot, RiskApprovalInput
from app.services import strategy_runtime_integration as sri
from app.services.execution_engine import PaperExecutionRequest


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


class DummyExecutionEngine:
    def execute_approved_signal(self, db, request):
        return type(
            "ExecutionResult",
            (),
            {"executed": True, "db_order_id": 9001},
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



def test_evaluate_from_candles_with_risk_and_execution_runs_execution_for_approved_signal(monkeypatch):
    monkeypatch.setattr(sri, "engine", DummyEngine())
    monkeypatch.setattr(sri, "risk_engine", DummyRiskEngine())
    monkeypatch.setattr(sri, "execution_engine", DummyExecutionEngine())

    result = sri.evaluate_from_candles_with_risk_and_execution(
        db=DummyDB(),
        bundle=DummyBundle(),
        approval_inputs_by_strategy={"momentum": _approval_input("BTC/USD")},
        execution_requests_by_strategy={
            "momentum": PaperExecutionRequest(
                signal_id=0,
                quantity=Decimal("1"),
                fill_price=Decimal("100"),
            )
        },
        account_id=7,
    )

    assert len(result) == 2
    assert result[0].strategy == "momentum"
    assert result[0].signal_id == 101
    assert result[0].approved is True
    assert result[0].executed is True
    assert result[0].execution_order_id == 9001
    assert result[0].execution_error is None

    assert result[1].strategy == "trend_continuation"
    assert result[1].executed is False
    assert result[1].execution_order_id is None
