from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.brokers import OrderRequest
from app.models import (
    Account,
    AssetClass,
    Balance,
    Fill,
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


@dataclass
class PaperExecutionRequest:
    signal_id: int
    quantity: Decimal
    fill_price: Decimal
    execution_metadata: dict[str, Any] | None = None


class ExecutionOutcome(str, Enum):
    EXECUTED = "executed"
    SKIPPED = "skipped"
    DUPLICATE = "duplicate"
    INVALID = "invalid"
    NOT_APPROVED = "not_approved"


class ExecutionSkipReason(str, Enum):
    SIGNAL_NOT_FOUND = "SIGNAL_NOT_FOUND"
    SIGNAL_NOT_APPROVED = "SIGNAL_NOT_APPROVED"
    SIGNAL_ALREADY_EXECUTED = "SIGNAL_ALREADY_EXECUTED"
    INVALID_QUANTITY = "INVALID_QUANTITY"
    INVALID_FILL_PRICE = "INVALID_FILL_PRICE"
    INVALID_METADATA = "INVALID_METADATA"
    MISSING_TIMEFRAME = "MISSING_TIMEFRAME"
    ACCOUNT_NOT_FOUND = "ACCOUNT_NOT_FOUND"
    EXECUTION_ERROR = "EXECUTION_ERROR"


@dataclass
class PaperExecutionResult:
    outcome: ExecutionOutcome
    signal_id: int
    account_id: int | None
    asset_class: AssetClass | None
    symbol: str | None
    quantity: Decimal | None
    fill_price: Decimal | None
    skip_reason: str | None
    execution_summary: str
    executed_at: datetime | None
    db_order_id: int | None
    db_fill_id: int | None
    broker_order_id: str | None
    order_status: str | None = None

    @property
    def executed(self) -> bool:
        return self.outcome is ExecutionOutcome.EXECUTED

    @property
    def skipped(self) -> bool:
        return self.outcome is not ExecutionOutcome.EXECUTED


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

    def _build_result(
        self,
        *,
        request: PaperExecutionRequest,
        signal: Signal | None,
        outcome: ExecutionOutcome,
        execution_summary: str,
        skip_reason: ExecutionSkipReason | None = None,
        executed_at: datetime | None = None,
        db_order_id: int | None = None,
        db_fill_id: int | None = None,
        broker_order_id: str | None = None,
        order_status: str | None = None,
    ) -> PaperExecutionResult:
        return PaperExecutionResult(
            outcome=outcome,
            signal_id=signal.id if signal is not None else request.signal_id,
            account_id=signal.account_id if signal is not None else None,
            asset_class=signal.asset_class if signal is not None else None,
            symbol=signal.symbol if signal is not None else None,
            quantity=request.quantity,
            fill_price=request.fill_price,
            skip_reason=skip_reason.value if skip_reason is not None else None,
            execution_summary=execution_summary,
            executed_at=executed_at,
            db_order_id=db_order_id,
            db_fill_id=db_fill_id,
            broker_order_id=broker_order_id,
            order_status=order_status,
        )

    def _validate_request(
        self,
        signal: Signal,
        request: PaperExecutionRequest,
    ) -> list[ExecutionSkipReason]:
        errors: list[ExecutionSkipReason] = []

        if not signal.timeframe:
            errors.append(ExecutionSkipReason.MISSING_TIMEFRAME)

        if request.quantity <= 0:
            errors.append(ExecutionSkipReason.INVALID_QUANTITY)

        if request.fill_price <= 0:
            errors.append(ExecutionSkipReason.INVALID_FILL_PRICE)

        try:
            json.dumps(request.execution_metadata or {})
        except (TypeError, ValueError):
            errors.append(ExecutionSkipReason.INVALID_METADATA)

        return errors

    def execute_approved_signal(
        self,
        db: Session,
        request: PaperExecutionRequest,
    ) -> PaperExecutionResult:
        signal = db.get(Signal, request.signal_id)

        if signal is None:
            return self._build_result(
                request=request,
                signal=None,
                outcome=ExecutionOutcome.SKIPPED,
                skip_reason=ExecutionSkipReason.SIGNAL_NOT_FOUND,
                execution_summary="signal not found for execution",
            )

        if signal.status == SignalStatus.EXECUTED:
            return self._build_result(
                request=request,
                signal=signal,
                outcome=ExecutionOutcome.DUPLICATE,
                skip_reason=ExecutionSkipReason.SIGNAL_ALREADY_EXECUTED,
                execution_summary="duplicate execution attempt skipped",
            )

        if signal.status is not SignalStatus.APPROVED:
            return self._build_result(
                request=request,
                signal=signal,
                outcome=ExecutionOutcome.NOT_APPROVED,
                skip_reason=ExecutionSkipReason.SIGNAL_NOT_APPROVED,
                execution_summary="signal not approved for execution",
            )

        validation_errors = self._validate_request(signal, request)
        if validation_errors:
            return self._build_result(
                request=request,
                signal=signal,
                outcome=ExecutionOutcome.INVALID,
                skip_reason=validation_errors[0],
                execution_summary="execution request failed validation",
            )

        account = db.get(Account, signal.account_id)
        if account is None:
            return self._build_result(
                request=request,
                signal=signal,
                outcome=ExecutionOutcome.SKIPPED,
                skip_reason=ExecutionSkipReason.ACCOUNT_NOT_FOUND,
                execution_summary="execution account not found",
            )

        broker = self.paper_account_service.get_broker(signal.asset_class)
        broker_order = broker.place_order(
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
            status=OrderStatus.FILLED,
        )
        db.add(order)
        db.flush()

        fill = Fill(
            account_id=account.id,
            order_id=order.id,
            symbol=signal.symbol,
            side=OrderSide.BUY,
            price=request.fill_price,
            quantity=request.quantity,
        )
        db.add(fill)
        db.flush()
        db.refresh(fill)

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

        return self._build_result(
            request=request,
            signal=signal,
            outcome=ExecutionOutcome.EXECUTED,
            execution_summary="paper execution completed",
            executed_at=fill.filled_at,
            db_order_id=order.id,
            db_fill_id=fill.id,
            broker_order_id=broker_order.id,
            order_status=OrderStatus.FILLED.value,
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

    def _apply_signal_filters(
        self,
        stmt: Select[tuple[Signal]],
        *,
        account_id: int | None = None,
        asset_class: AssetClass | None = None,
        symbol: str | None = None,
    ) -> Select[tuple[Signal]]:
        if account_id is not None:
            stmt = stmt.where(Signal.account_id == account_id)

        if asset_class is not None:
            stmt = stmt.where(Signal.asset_class == asset_class)

        if symbol:
            stmt = stmt.where(Signal.symbol == symbol.upper())

        return stmt

    def list_recent_executions(
        self,
        db: Session,
        limit: int = 50,
        *,
        account_id: int | None = None,
        asset_class: AssetClass | None = None,
        symbol: str | None = None,
    ) -> list[ExecutionAuditRecord]:
        stmt = (
            select(Signal)
            .where(Signal.status == SignalStatus.EXECUTED)
            .order_by(Signal.created_at.desc())
            .limit(limit)
        )
        stmt = self._apply_signal_filters(
            stmt,
            account_id=account_id,
            asset_class=asset_class,
            symbol=symbol,
        )
        signals = db.execute(stmt).scalars().all()

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

    def get_execution_summary(
        self,
        db: Session,
        *,
        account_id: int | None = None,
        asset_class: AssetClass | None = None,
        symbol: str | None = None,
    ) -> dict[str, int]:
        counts = {
            "new": 0,
            "approved": 0,
            "rejected": 0,
            "executed": 0,
            "recent_execution_count": 0,
            "recent_skipped_count": 0,
        }

        stmt = self._apply_signal_filters(
            select(Signal),
            account_id=account_id,
            asset_class=asset_class,
            symbol=symbol,
        )
        signals = db.execute(stmt).scalars().all()

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
