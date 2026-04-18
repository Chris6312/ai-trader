from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.brokers import BrokerError, OrderRequest, OrderSnapshot
from app.models import (
    Account,
    AssetClass,
    Balance,
    Fill,
    FillSide,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    PositionSide,
    Signal,
    SignalStatus,
)
from app.services.paper_accounts import PaperAccountService


class ExecutionError(Exception):
    """Raised when a paper execution request cannot be completed."""


@dataclass(slots=True)
class PaperExecutionRequest:
    signal_id: int
    quantity: Decimal
    fill_price: Decimal
    side: OrderSide = OrderSide.BUY
    order_type: OrderType = OrderType.MARKET
    submitted_at: datetime | None = None
    execution_metadata: dict[str, Any] | None = None


@dataclass(slots=True)
class PaperExecutionResult:
    signal_id: int
    executed: bool
    account_id: int
    asset_class: AssetClass
    broker_order_id: str | None
    order_status: OrderStatus | None
    db_order_id: int | None
    db_fill_id: int | None
    quantity: Decimal
    fill_price: Decimal
    reasoning: dict[str, Any]


class PaperExecutionEngine:
    def __init__(self, paper_account_service: PaperAccountService | None = None) -> None:
        self._paper_account_service = paper_account_service or PaperAccountService()

    def execute_approved_signal(
        self,
        db: Session,
        request: PaperExecutionRequest,
    ) -> PaperExecutionResult:
        signal = db.get(Signal, request.signal_id)
        if signal is None:
            raise ExecutionError(f"Signal {request.signal_id} was not found.")
        if signal.account_id is None:
            raise ExecutionError("Approved signal must be linked to an account before execution.")
        if signal.status is not SignalStatus.APPROVED:
            raise ExecutionError(
                f"Signal {signal.id} must be in approved status before execution. Current status: {signal.status.value}."
            )
        if request.quantity <= Decimal("0"):
            raise ExecutionError("Execution quantity must be greater than zero.")
        if request.fill_price <= Decimal("0"):
            raise ExecutionError("Execution fill price must be greater than zero.")

        account = db.get(Account, signal.account_id)
        if account is None:
            raise ExecutionError(f"Account {signal.account_id} was not found.")

        asset_class = self._coerce_asset_class(signal.asset_class)
        if account.asset_class is not asset_class:
            raise ExecutionError(
                f"Signal asset class {asset_class.value} does not match account asset class {account.asset_class.value}."
            )

        broker = self._paper_account_service.get_broker(asset_class)
        submitted_at = request.submitted_at or datetime.now(UTC)

        try:
            broker_order = broker.place_order(
                OrderRequest(
                    symbol=signal.symbol,
                    side=request.side,
                    order_type=request.order_type,
                    quantity=request.quantity,
                ),
                fill_price=request.fill_price,
                submitted_at=submitted_at,
            )
        except BrokerError as exc:
            raise ExecutionError(str(exc)) from exc

        db_order = self._persist_order(db, account_id=account.id, asset_class=asset_class, snapshot=broker_order)
        db_fill = self._persist_fill(db, account_id=account.id, order_id=db_order.id, snapshot=broker_order)
        self.reconcile_account_state(db, account_id=account.id, asset_class=asset_class)

        signal.status = SignalStatus.EXECUTED
        signal.reasoning = json.dumps(
            self._merge_execution_reasoning(
                existing_reasoning=signal.reasoning,
                signal=signal,
                request=request,
                broker_order=broker_order,
                db_order_id=db_order.id,
                db_fill_id=db_fill.id if db_fill is not None else None,
            ),
            default=str,
            sort_keys=True,
        )

        db.add(signal)
        db.commit()
        db.refresh(signal)

        reasoning_payload = self._load_reasoning(signal.reasoning)
        return PaperExecutionResult(
            signal_id=signal.id,
            executed=True,
            account_id=account.id,
            asset_class=asset_class,
            broker_order_id=broker_order.id,
            order_status=broker_order.status,
            db_order_id=db_order.id,
            db_fill_id=db_fill.id if db_fill is not None else None,
            quantity=broker_order.quantity,
            fill_price=broker_order.average_fill_price or request.fill_price,
            reasoning=reasoning_payload,
        )

    def reconcile_account_state(self, db: Session, *, account_id: int, asset_class: AssetClass) -> None:
        account = db.get(Account, account_id)
        if account is None:
            raise ExecutionError(f"Account {account_id} was not found.")
        if account.asset_class is not asset_class:
            raise ExecutionError(
                f"Cannot reconcile {asset_class.value} state into {account.asset_class.value} account {account_id}."
            )

        broker = self._paper_account_service.get_broker(asset_class)
        balance_snapshot = broker.get_balance()
        balance = db.execute(
            select(Balance).where(Balance.account_id == account_id, Balance.currency == account.base_currency)
        ).scalar_one_or_none()
        if balance is None:
            balance = Balance(account_id=account_id, currency=account.base_currency)
            db.add(balance)

        balance.total = balance_snapshot.total
        balance.available = balance_snapshot.available
        balance.reserved = balance_snapshot.reserved
        balance.updated_at = balance_snapshot.updated_at

        existing_positions = {
            position.symbol: position
            for position in db.execute(
                select(Position).where(Position.account_id == account_id, Position.asset_class == asset_class)
            ).scalars()
        }
        broker_positions = {position.symbol: position for position in broker.list_positions()}

        for symbol, broker_position in broker_positions.items():
            db_position = existing_positions.pop(symbol, None)
            if db_position is None:
                db_position = Position(
                    account_id=account_id,
                    symbol=symbol,
                    asset_class=asset_class,
                    side=PositionSide.LONG,
                )
                db.add(db_position)

            db_position.quantity = broker_position.quantity
            db_position.average_entry_price = broker_position.average_entry_price
            db_position.market_value = broker_position.market_value
            db_position.unrealized_pnl = broker_position.unrealized_pnl
            db_position.updated_at = broker_position.updated_at

        for stale_position in existing_positions.values():
            db.delete(stale_position)

        db.commit()

    def _persist_order(
        self,
        db: Session,
        *,
        account_id: int,
        asset_class: AssetClass,
        snapshot: OrderSnapshot,
    ) -> Order:
        order = Order(
            account_id=account_id,
            symbol=snapshot.symbol,
            asset_class=asset_class,
            side=snapshot.side,
            order_type=snapshot.order_type,
            status=snapshot.status,
            quantity=snapshot.quantity,
            limit_price=snapshot.limit_price,
            stop_price=snapshot.stop_price,
            submitted_at=snapshot.created_at,
            updated_at=snapshot.updated_at,
        )
        db.add(order)
        db.flush()
        return order

    def _persist_fill(
        self,
        db: Session,
        *,
        account_id: int,
        order_id: int,
        snapshot: OrderSnapshot,
    ) -> Fill | None:
        if snapshot.status is not OrderStatus.FILLED or snapshot.average_fill_price is None:
            return None

        fill = Fill(
            account_id=account_id,
            order_id=order_id,
            symbol=snapshot.symbol,
            side=FillSide(snapshot.side.value),
            quantity=snapshot.filled_quantity,
            price=snapshot.average_fill_price,
            fee=snapshot.fee_paid,
            filled_at=snapshot.updated_at,
        )
        db.add(fill)
        db.flush()
        return fill

    def _merge_execution_reasoning(
        self,
        *,
        existing_reasoning: str | None,
        signal: Signal,
        request: PaperExecutionRequest,
        broker_order: OrderSnapshot,
        db_order_id: int,
        db_fill_id: int | None,
    ) -> dict[str, Any]:
        payload = self._load_reasoning(existing_reasoning)
        payload["execution"] = {
            "executed": True,
            "summary": "paper execution completed",
            "signal_id": signal.id,
            "account_id": signal.account_id,
            "db_order_id": db_order_id,
            "db_fill_id": db_fill_id,
            "broker_order_id": broker_order.id,
            "symbol": signal.symbol,
            "asset_class": self._coerce_asset_class(signal.asset_class).value,
            "side": request.side.value,
            "order_type": request.order_type.value,
            "timeframe": signal.timeframe,
            "quantity": str(broker_order.quantity),
            "fill_price": str(broker_order.average_fill_price or request.fill_price),
            "status": broker_order.status.value,
            "submitted_at": (request.submitted_at or broker_order.created_at).isoformat(),
            "metadata": request.execution_metadata or {},
        }
        return payload

    def _load_reasoning(self, raw_reasoning: str | None) -> dict[str, Any]:
        if not raw_reasoning:
            return {}
        try:
            loaded = json.loads(raw_reasoning)
        except json.JSONDecodeError:
            return {"raw_reasoning": raw_reasoning}
        return loaded if isinstance(loaded, dict) else {"raw_reasoning": loaded}

    def _coerce_asset_class(self, value: AssetClass | str) -> AssetClass:
        return value if isinstance(value, AssetClass) else AssetClass(value)
