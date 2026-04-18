from __future__ import annotations

import json
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import (
    Account,
    AccountType,
    AssetClass,
    Balance,
    Fill,
    Order,
    Position,
    Signal,
    SignalStatus,
)
from app.services.execution_engine import (
    ExecutionAuditRecord,
    ExecutionOutcome,
    ExecutionSkipReason,
    PaperExecutionEngine,
    PaperExecutionRequest,
)
from app.services.paper_accounts import PaperAccountService


@pytest.fixture
def db_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    from app.db.base import Base

    Base.metadata.create_all(engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def paper_account_service() -> PaperAccountService:
    return PaperAccountService(stock_initial_cash=Decimal("10000"), crypto_initial_cash=Decimal("10000"))


def _create_account(db: Session, *, asset_class: AssetClass) -> Account:
    account = Account(
        name=f"{asset_class.value}-paper",
        account_type=AccountType.PAPER,
        asset_class=asset_class,
        base_currency="USD",
        is_active=True,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def _create_signal(
    db: Session,
    *,
    account_id: int | None,
    asset_class: AssetClass,
    status: SignalStatus,
    symbol: str | None = None,
    timeframe: str = "1h",
) -> Signal:
    resolved_symbol = symbol or ("AAPL" if asset_class is AssetClass.STOCK else "BTCUSD")
    signal = Signal(
        account_id=account_id,
        symbol=resolved_symbol,
        asset_class=asset_class,
        strategy_name="momentum",
        timeframe=timeframe,
        status=status,
        confidence=Decimal("0.90"),
        reasoning=json.dumps({"risk_approval": {"approved": status is SignalStatus.APPROVED}}),
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
    return signal


def test_execute_approved_signal_returns_normalized_execution_result(
    db_session: Session,
    paper_account_service: PaperAccountService,
) -> None:
    account = _create_account(db_session, asset_class=AssetClass.STOCK)
    signal = _create_signal(
        db_session,
        account_id=account.id,
        asset_class=AssetClass.STOCK,
        status=SignalStatus.APPROVED,
    )
    engine = PaperExecutionEngine(paper_account_service=paper_account_service)

    result = engine.execute_approved_signal(
        db_session,
        PaperExecutionRequest(
            signal_id=signal.id,
            quantity=Decimal("10"),
            fill_price=Decimal("100"),
            execution_metadata={"source": "phase_10_test"},
        ),
    )

    assert result.outcome is ExecutionOutcome.EXECUTED
    assert result.executed is True
    assert result.skipped is False
    assert result.signal_id == signal.id
    assert result.account_id == account.id
    assert result.asset_class is AssetClass.STOCK
    assert result.symbol == "AAPL"
    assert result.quantity == Decimal("10")
    assert result.fill_price == Decimal("100")
    assert result.execution_summary == "paper execution completed"
    assert result.executed_at is not None
    assert result.db_order_id is not None
    assert result.db_fill_id is not None
    assert result.broker_order_id is not None
    assert result.order_status == "filled"

    refreshed_signal = db_session.get(Signal, signal.id)
    assert refreshed_signal is not None
    assert refreshed_signal.status is SignalStatus.EXECUTED

    reasoning = json.loads(refreshed_signal.reasoning or "{}")
    assert reasoning["execution"]["status"] == "executed"
    assert reasoning["execution"]["summary"] == "paper execution completed"
    assert reasoning["execution"]["timeframe"] == "1h"
    assert reasoning["execution"]["quantity"] == "10"
    assert reasoning["execution"]["fill_price"] == "100"
    assert reasoning["execution"]["skip_reason"] is None
    assert reasoning["execution"]["broker_order_id"] == result.broker_order_id
    assert reasoning["execution"]["db_order_id"] == result.db_order_id
    assert reasoning["execution"]["db_fill_id"] == result.db_fill_id
    assert reasoning["execution"]["executed_at"] is not None
    assert reasoning["execution"]["validation"]["valid"] is True
    assert reasoning["execution"]["validation"]["errors"] == []
    assert reasoning["execution"]["metadata"] == {"source": "phase_10_test"}

    balance = db_session.execute(select(Balance).where(Balance.account_id == account.id)).scalar_one()
    assert balance.total == Decimal("9000.00000000")
    assert balance.available == Decimal("9000.00000000")

    order = db_session.execute(select(Order).where(Order.account_id == account.id)).scalar_one()
    assert order.symbol == "AAPL"
    assert order.quantity == Decimal("10.00000000")

    fill = db_session.execute(select(Fill).where(Fill.account_id == account.id)).scalar_one()
    assert fill.price == Decimal("100.00000000")
    assert fill.quantity == Decimal("10.00000000")

    position = db_session.execute(select(Position).where(Position.account_id == account.id)).scalar_one()
    assert position.symbol == "AAPL"
    assert position.quantity == Decimal("10.00000000")
    assert position.average_entry_price == Decimal("100.00000000")


def test_execute_approved_signal_is_idempotent_for_already_executed_signal(
    db_session: Session,
    paper_account_service: PaperAccountService,
) -> None:
    account = _create_account(db_session, asset_class=AssetClass.STOCK)
    signal = _create_signal(
        db_session,
        account_id=account.id,
        asset_class=AssetClass.STOCK,
        status=SignalStatus.APPROVED,
    )
    engine = PaperExecutionEngine(paper_account_service=paper_account_service)

    first_result = engine.execute_approved_signal(
        db_session,
        PaperExecutionRequest(
            signal_id=signal.id,
            quantity=Decimal("2"),
            fill_price=Decimal("100"),
        ),
    )
    second_result = engine.execute_approved_signal(
        db_session,
        PaperExecutionRequest(
            signal_id=signal.id,
            quantity=Decimal("2"),
            fill_price=Decimal("100"),
        ),
    )

    assert first_result.outcome is ExecutionOutcome.EXECUTED
    assert second_result.outcome is ExecutionOutcome.DUPLICATE
    assert second_result.executed is False
    assert second_result.skipped is True
    assert second_result.skip_reason == ExecutionSkipReason.SIGNAL_ALREADY_EXECUTED.value
    assert second_result.execution_summary == "duplicate execution attempt skipped"

    refreshed_signal = db_session.get(Signal, signal.id)
    assert refreshed_signal is not None
    reasoning = json.loads(refreshed_signal.reasoning or "{}")
    assert reasoning["execution"]["status"] == "duplicate"
    assert reasoning["execution"]["skip_reason"] == ExecutionSkipReason.SIGNAL_ALREADY_EXECUTED.value
    assert reasoning["execution"]["validation"]["valid"] is True

    orders = db_session.execute(select(Order).where(Order.account_id == account.id)).scalars().all()
    fills = db_session.execute(select(Fill).where(Fill.account_id == account.id)).scalars().all()
    assert len(orders) == 1
    assert len(fills) == 1


def test_execute_approved_signal_returns_not_approved_outcome(
    db_session: Session,
    paper_account_service: PaperAccountService,
) -> None:
    account = _create_account(db_session, asset_class=AssetClass.STOCK)
    signal = _create_signal(
        db_session,
        account_id=account.id,
        asset_class=AssetClass.STOCK,
        status=SignalStatus.REJECTED,
    )
    engine = PaperExecutionEngine(paper_account_service=paper_account_service)

    result = engine.execute_approved_signal(
        db_session,
        PaperExecutionRequest(
            signal_id=signal.id,
            quantity=Decimal("1"),
            fill_price=Decimal("100"),
        ),
    )

    assert result.outcome is ExecutionOutcome.NOT_APPROVED
    assert result.executed is False
    assert result.skipped is True
    assert result.skip_reason == ExecutionSkipReason.SIGNAL_NOT_APPROVED.value
    assert result.execution_summary == "signal not approved for execution"

    refreshed_signal = db_session.get(Signal, signal.id)
    assert refreshed_signal is not None
    reasoning = json.loads(refreshed_signal.reasoning or "{}")
    assert reasoning["execution"]["status"] == "not_approved"
    assert reasoning["execution"]["skip_reason"] == ExecutionSkipReason.SIGNAL_NOT_APPROVED.value


def test_execute_approved_signal_returns_invalid_outcome_for_validation_errors(
    db_session: Session,
    paper_account_service: PaperAccountService,
) -> None:
    account = _create_account(db_session, asset_class=AssetClass.STOCK)
    signal = _create_signal(
        db_session,
        account_id=account.id,
        asset_class=AssetClass.STOCK,
        status=SignalStatus.APPROVED,
        timeframe="",
    )
    engine = PaperExecutionEngine(paper_account_service=paper_account_service)

    result = engine.execute_approved_signal(
        db_session,
        PaperExecutionRequest(
            signal_id=signal.id,
            quantity=Decimal("0"),
            fill_price=Decimal("0"),
        ),
    )

    assert result.outcome is ExecutionOutcome.INVALID
    assert result.executed is False

    refreshed_signal = db_session.get(Signal, signal.id)
    assert refreshed_signal is not None
    reasoning = json.loads(refreshed_signal.reasoning or "{}")
    assert reasoning["execution"]["status"] == "invalid"
    assert reasoning["execution"]["skip_reason"] == ExecutionSkipReason.MISSING_TIMEFRAME.value
    assert reasoning["execution"]["validation"]["valid"] is False
    assert reasoning["execution"]["validation"]["errors"] == [
        ExecutionSkipReason.MISSING_TIMEFRAME.value,
        ExecutionSkipReason.INVALID_QUANTITY.value,
        ExecutionSkipReason.INVALID_FILL_PRICE.value,
    ]
    assert result.skipped is True
    assert result.execution_summary == "execution request failed validation"
    assert result.skip_reason == ExecutionSkipReason.MISSING_TIMEFRAME.value
    
    


def test_execute_approved_signal_returns_skipped_outcome_when_signal_missing(
    db_session: Session,
    paper_account_service: PaperAccountService,
) -> None:
    engine = PaperExecutionEngine(paper_account_service=paper_account_service)

    result = engine.execute_approved_signal(
        db_session,
        PaperExecutionRequest(
            signal_id=9999,
            quantity=Decimal("1"),
            fill_price=Decimal("100"),
        ),
    )

    assert result.outcome is ExecutionOutcome.SKIPPED
    assert result.executed is False
    assert result.skipped is True
    assert result.signal_id == 9999
    assert result.account_id is None
    assert result.asset_class is None
    assert result.symbol is None
    assert result.skip_reason == ExecutionSkipReason.SIGNAL_NOT_FOUND.value
    assert result.execution_summary == "signal not found for execution"


def test_execute_approved_signal_returns_stable_reason_code_for_invalid_metadata(
    db_session: Session,
    paper_account_service: PaperAccountService,
) -> None:
    account = _create_account(db_session, asset_class=AssetClass.STOCK)
    signal = _create_signal(
        db_session,
        account_id=account.id,
        asset_class=AssetClass.STOCK,
        status=SignalStatus.APPROVED,
    )
    engine = PaperExecutionEngine(paper_account_service=paper_account_service)

    result = engine.execute_approved_signal(
        db_session,
        PaperExecutionRequest(
            signal_id=signal.id,
            quantity=Decimal("1"),
            fill_price=Decimal("100"),
            execution_metadata={"when": Decimal("1.5")},
        ),
    )

    assert result.outcome is ExecutionOutcome.INVALID
    assert result.skip_reason == ExecutionSkipReason.INVALID_METADATA.value
    assert result.execution_summary == "execution request failed validation"

    refreshed_signal = db_session.get(Signal, signal.id)
    assert refreshed_signal is not None
    reasoning = json.loads(refreshed_signal.reasoning or "{}")
    assert reasoning["execution"]["metadata"] == {}
    assert reasoning["execution"]["validation"]["errors"] == [ExecutionSkipReason.INVALID_METADATA.value]


def test_list_recent_executions_returns_execution_audit_records(
    db_session: Session,
    paper_account_service: PaperAccountService,
) -> None:
    account = _create_account(db_session, asset_class=AssetClass.STOCK)
    signal = _create_signal(
        db_session,
        account_id=account.id,
        asset_class=AssetClass.STOCK,
        status=SignalStatus.APPROVED,
    )
    engine = PaperExecutionEngine(paper_account_service=paper_account_service)

    engine.execute_approved_signal(
        db_session,
        PaperExecutionRequest(
            signal_id=signal.id,
            quantity=Decimal("3"),
            fill_price=Decimal("150.50"),
        ),
    )

    records = engine.list_recent_executions(db_session, limit=10)

    assert len(records) == 1
    record = records[0]
    assert isinstance(record, ExecutionAuditRecord)
    assert record.signal_id == signal.id
    assert record.account_id == account.id
    assert record.symbol == "AAPL"
    assert record.asset_class is AssetClass.STOCK
    assert record.strategy_name == "momentum"
    assert record.timeframe == "1h"
    assert record.status is SignalStatus.EXECUTED
    assert record.quantity == Decimal("3")
    assert record.fill_price == Decimal("150.50")
    assert record.execution_summary == "paper execution completed"
    assert record.broker_order_id is not None
    assert record.db_order_id is not None
    assert record.db_fill_id is not None
    assert record.executed_at is not None
    assert record.skipped is False
    assert record.skip_reason is None


def test_get_execution_summary_counts_executed_signals(
    db_session: Session,
    paper_account_service: PaperAccountService,
) -> None:
    account = _create_account(db_session, asset_class=AssetClass.STOCK)
    approved_signal = _create_signal(
        db_session,
        account_id=account.id,
        asset_class=AssetClass.STOCK,
        status=SignalStatus.APPROVED,
        symbol="MSFT",
    )
    _create_signal(
        db_session,
        account_id=account.id,
        asset_class=AssetClass.STOCK,
        status=SignalStatus.REJECTED,
        symbol="NVDA",
    )
    _create_signal(
        db_session,
        account_id=account.id,
        asset_class=AssetClass.STOCK,
        status=SignalStatus.NEW,
        symbol="TSLA",
    )

    engine = PaperExecutionEngine(paper_account_service=paper_account_service)
    engine.execute_approved_signal(
        db_session,
        PaperExecutionRequest(
            signal_id=approved_signal.id,
            quantity=Decimal("1"),
            fill_price=Decimal("250"),
        ),
    )

    summary = engine.get_execution_summary(db_session)

    assert summary["new"] == 1
    assert summary["approved"] == 0
    assert summary["rejected"] == 1
    assert summary["executed"] == 1
    assert summary["recent_execution_count"] == 1
    assert summary["recent_skipped_count"] == 0
