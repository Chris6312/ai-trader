from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.execution_engine import PaperExecutionEngine

router = APIRouter(prefix="/api/execution", tags=["execution"])


def _decimal_to_compact_string(value: Decimal) -> str:
    normalized = value.normalize()
    text = format(normalized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _decimal_to_stock_price_string(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")


def _decimal_to_crypto_price_string(value: Decimal) -> str:
    return _decimal_to_compact_string(value)


@router.get("/recent")
def get_recent_executions(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    service = PaperExecutionEngine()
    records = service.list_recent_executions(db, limit=limit)
    return [
        {
            "signal_id": record.signal_id,
            "account_id": record.account_id,
            "symbol": record.symbol,
            "asset_class": record.asset_class.value,
            "strategy_name": record.strategy_name,
            "timeframe": record.timeframe,
            "status": record.status.value,
            "broker_order_id": record.broker_order_id,
            "db_order_id": record.db_order_id,
            "db_fill_id": record.db_fill_id,
            "quantity": _decimal_to_compact_string(record.quantity),
            "fill_price": (
                _decimal_to_stock_price_string(record.fill_price)
                if record.asset_class.value == "stock"
                else _decimal_to_crypto_price_string(record.fill_price)
            ),
            "execution_summary": record.execution_summary,
            "executed_at": record.executed_at,
            "created_at": record.created_at,
            "skipped": record.skipped,
            "skip_reason": record.skip_reason,
        }
        for record in records
    ]


@router.get("/summary")
def get_execution_summary(db: Session = Depends(get_db)) -> dict[str, int]:
    service = PaperExecutionEngine()
    return service.get_execution_summary(db)