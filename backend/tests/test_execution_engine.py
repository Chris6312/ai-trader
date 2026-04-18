from __future__ import annotations

import json
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.brokers import OrderRequest
from app.db.base import Base
from app.models import Account, AccountType, AssetClass, Balance, Fill, Order, OrderSide, OrderType, Position, Signal, SignalStatus
from app.services.execution_engine import ExecutionError, PaperExecutionEngine, PaperExecutionRequest
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


def _create_signal(db: Session, *, account_id: int, asset_class: AssetClass, status: SignalStatus) -> Signal:
    signal = Signal(
        account_id=account_id,
        symbol="AAPL" if asset_class is AssetClass.STOCK else "BTCUSD",
        asset_class=asset_class,
        strategy_name="momentum",
        timeframe="1h",
        status=status,
        confidence=Decimal("0.90"),
        reasoning=json.dumps({"risk_approval": {"approved": status is SignalStatus.APPROVED}}),
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
    return signal


def test_execute_approved_signal_persists_order_fill_balance_and_position(
    db_session: Session,
    paper_account_service: PaperAccountService,
) -> None:
    account = _create_account(db_session, asset_class=AssetClass.STOCK)
    signal = _create_signal(db_session, account_id=account.id, asset_class=AssetClass.STOCK, status=SignalStatus.APPROVED)
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

    assert result.executed is True
    assert result.db_order_id is not None
    assert result.db_fill_id is not None
    assert result.order_status is not None and result.order_status.value == "filled"

    refreshed_signal = db_session.get(Signal, signal.id)
    assert refreshed_signal is not None
    assert refreshed_signal.status is SignalStatus.EXECUTED
    reasoning = json.loads(refreshed_signal.reasoning or "{}")
    assert reasoning["execution"]["summary"] == "paper execution completed"
    assert reasoning["execution"]["timeframe"] == "1h"

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


def test_execute_approved_signal_rejects_non_approved_signal(
    db_session: Session,
    paper_account_service: PaperAccountService,
) -> None:
    account = _create_account(db_session, asset_class=AssetClass.STOCK)
    signal = _create_signal(db_session, account_id=account.id, asset_class=AssetClass.STOCK, status=SignalStatus.REJECTED)
    engine = PaperExecutionEngine(paper_account_service=paper_account_service)

    with pytest.raises(ExecutionError, match="must be in approved status"):
        engine.execute_approved_signal(
            db_session,
            PaperExecutionRequest(
                signal_id=signal.id,
                quantity=Decimal("1"),
                fill_price=Decimal("100"),
            ),
        )


def test_reconcile_account_state_replaces_stale_positions(
    db_session: Session,
    paper_account_service: PaperAccountService,
) -> None:
    account = _create_account(db_session, asset_class=AssetClass.CRYPTO)
    db_session.add(
        Position(
            account_id=account.id,
            symbol="ETHUSD",
            asset_class=AssetClass.CRYPTO,
            quantity=Decimal("1"),
            average_entry_price=Decimal("2000"),
            market_value=Decimal("2000"),
            unrealized_pnl=Decimal("0"),
        )
    )
    db_session.commit()

    broker = paper_account_service.get_broker(AssetClass.CRYPTO)
    broker.place_order(
        OrderRequest(
            symbol="BTCUSD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.5"),
        ),
        fill_price=Decimal("10000"),
    )

    engine = PaperExecutionEngine(paper_account_service=paper_account_service)
    engine.reconcile_account_state(db_session, account_id=account.id, asset_class=AssetClass.CRYPTO)

    positions = db_session.execute(select(Position).where(Position.account_id == account.id)).scalars().all()
    assert len(positions) == 1
    assert positions[0].symbol == "BTCUSD"
    assert positions[0].quantity == Decimal("0.50000000")

    balance = db_session.execute(select(Balance).where(Balance.account_id == account.id)).scalar_one()
    assert balance.total == Decimal("4987.50000000")
    assert balance.available == Decimal("4987.50000000")


def test_execute_approved_signal_is_idempotent_for_already_executed_signal(
    db_session: Session,
    paper_account_service: PaperAccountService,
) -> None:
    account = _create_account(db_session, asset_class=AssetClass.STOCK)
    signal = _create_signal(db_session, account_id=account.id, asset_class=AssetClass.STOCK, status=SignalStatus.APPROVED)
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

    assert first_result.executed is True
    assert second_result.executed is False
    assert second_result.skipped is True
    assert second_result.skip_reason == "signal_already_executed"
    assert second_result.db_order_id == first_result.db_order_id
    assert second_result.db_fill_id == first_result.db_fill_id

    orders = db_session.execute(select(Order).where(Order.account_id == account.id)).scalars().all()
    fills = db_session.execute(select(Fill).where(Fill.account_id == account.id)).scalars().all()
    assert len(orders) == 1
    assert len(fills) == 1
