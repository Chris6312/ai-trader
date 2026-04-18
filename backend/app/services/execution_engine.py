from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.brokers import OrderRequest
from app.models import (
    Account,
    AssetClass,
    Balance,
    Fill,
    Order,
    OrderSide,
    OrderType,
    Position,
    PositionSide,
    Signal,
    SignalStatus,
)
from app.services.paper_accounts import PaperAccountService


@dataclass
class PaperExecutionRequest:
    signal_id: int
    quantity: Decimal
    fill_price: Decimal
    execution_metadata: dict[str, Any] | None = None


@dataclass
class PaperExecutionResult:
    executed: bool
    skipped: bool
    skip_reason: str | None
    db_order_id: int | None
    db_fill_id: int | None
    order_status: str | None


@dataclass
class ExecutionAuditRecord:
    signal_id: int
    account_id: int
    symbol: str
    asset_class: AssetClass
    strategy_name: str
    timeframe: str
    status: SignalStatus
    quantity: Decimal
    fill_price: Decimal
    execution_summary: str
    broker_order_id: str | None
    db_order_id: int | None
    db_fill_id: int | None
    created_at: datetime | None
    executed_at: datetime | None
    skipped: bool
    skip_reason: str | None


class ExecutionError(Exception):
    pass


class PaperExecutionEngine:
    def __init__(self, paper_account_service: PaperAccountService | None = None):
        self.paper_account_service = paper_account_service or PaperAccountService()

    def _validate_request(
        self,
        signal: Signal | None,
        request: PaperExecutionRequest,
    ) -> tuple[bool, list[str]]:
        errors: list[str] = []

        if signal is None:
            errors.append("execution_signal_not_found")
            return False, errors

        if signal.status == SignalStatus.EXECUTED:
            return True, []

        if signal.status is not SignalStatus.APPROVED:
            errors.append("execution_signal_not_approved")

        if not signal.timeframe:
            errors.append("execution_missing_timeframe")

        if request.quantity <= 0:
            errors.append("execution_invalid_quantity")

        if request.fill_price <= 0:
            errors.append("execution_invalid_price")

        try:
            json.dumps(request.execution_metadata or {})
        except (TypeError, ValueError):
            errors.append("execution_invalid_metadata")

        return len(errors) == 0, errors

    def execute_approved_signal(
        self,
        db: Session,
        request: PaperExecutionRequest,
    ) -> PaperExecutionResult:
        signal = db.get(Signal, request.signal_id)

        if signal is not None and signal.status == SignalStatus.EXECUTED:
            return PaperExecutionResult(
                executed=False,
                skipped=True,
                skip_reason="signal_already_executed",
                db_order_id=None,
                db_fill_id=None,
                order_status=None,
            )

        valid, errors = self._validate_request(signal, request)

        if not valid:
            return PaperExecutionResult(
                executed=False,
                skipped=True,
                skip_reason=";".join(errors),
                db_order_id=None,
                db_fill_id=None,
                order_status=None,
            )

        assert signal is not None
        account = db.get(Account, signal.account_id)
        if account is None:
            return PaperExecutionResult(
                executed=False,
                skipped=True,
                skip_reason="execution_account_not_found",
                db_order_id=None,
                db_fill_id=None,
                order_status=None,
            )

        broker = self.paper_account_service.get_broker(signal.asset_class)

        broker.place_order(
            OrderRequest(
                symbol=signal.symbol,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=request.quantity,
            ),
            fill_price=request.fill_price,
        )

        order = Order(
            account_id=account.id,
            symbol=signal.symbol,
            asset_class=signal.asset_class,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=request.quantity,
            status="filled",
        )
        db.add(order)
        db.flush()

        fill = Fill(
            account_id=account.id,
            order_id=order.id,
            symbol=signal.symbol,
            side=OrderSide.BUY,   # <-- REQUIRED
            price=request.fill_price,
            quantity=request.quantity,
        )
        db.add(fill)

        self.reconcile_account_state(db, account.id, signal.asset_class)

        reasoning = json.loads(signal.reasoning or "{}")
        reasoning["execution"] = {
            "summary": "paper execution completed",
            "timeframe": signal.timeframe,
            "quantity": str(request.quantity),
            "fill_price": str(request.fill_price),
            "validation": {
                "valid": True,
                "errors": [],
            },
            "metadata": dict(request.execution_metadata or {}),
        }

        signal.reasoning = json.dumps(reasoning)
        signal.status = SignalStatus.EXECUTED

        db.commit()

        return PaperExecutionResult(
            executed=True,
            skipped=False,
            skip_reason=None,
            db_order_id=order.id,
            db_fill_id=fill.id,
            order_status="filled",
        )

    def reconcile_account_state(
        self,
        db: Session,
        account_id: int,
        asset_class: AssetClass,
    ) -> None:
        broker = self.paper_account_service.get_broker(asset_class)

        account = db.get(Account, account_id)
        if account is None:
            raise ExecutionError(f"Account {account_id} was not found.")

        balance_snapshot = broker.get_balance()
        balance = db.execute(
            select(Balance).where(
                Balance.account_id == account_id,
                Balance.currency == account.base_currency,
            )
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
                select(Position).where(
                    Position.account_id == account_id,
                    Position.asset_class == asset_class,
                )
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

    def list_recent_executions(
        self,
        db: Session,
        limit: int = 50,
    ) -> list[ExecutionAuditRecord]:
        signals = (
            db.execute(
                select(Signal)
                .where(Signal.status == SignalStatus.EXECUTED)
                .order_by(Signal.created_at.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )

        results: list[ExecutionAuditRecord] = []

        for s in signals:
            reasoning = json.loads(s.reasoning or "{}")
            exec_block = reasoning.get("execution", {})

            results.append(
                ExecutionAuditRecord(
                    signal_id=s.id,
                    account_id=s.account_id,
                    symbol=s.symbol,
                    asset_class=s.asset_class,
                    strategy_name=s.strategy_name,
                    timeframe=s.timeframe,
                    status=s.status,
                    quantity=Decimal(str(exec_block.get("quantity", "0"))),
                    fill_price=Decimal(str(exec_block.get("fill_price", "0"))),
                    execution_summary=str(exec_block.get("summary", "")),
                    broker_order_id=None,
                    db_order_id=None,
                    db_fill_id=None,
                    created_at=s.created_at,
                    executed_at=s.created_at,
                    skipped=False,
                    skip_reason=None,
                )
            )

        return results

    def get_execution_summary(self, db: Session) -> dict[str, int]:
        counts = {
            "new": 0,
            "approved": 0,
            "rejected": 0,
            "executed": 0,
            "recent_execution_count": 0,
            "recent_skipped_count": 0,
        }

        signals = db.execute(select(Signal)).scalars().all()

        for s in signals:
            if s.status == SignalStatus.NEW:
                counts["new"] += 1
            elif s.status == SignalStatus.APPROVED:
                counts["approved"] += 1
            elif s.status == SignalStatus.REJECTED:
                counts["rejected"] += 1
            elif s.status == SignalStatus.EXECUTED:
                counts["executed"] += 1

        counts["recent_execution_count"] = counts["executed"]
        return counts