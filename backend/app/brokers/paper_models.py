from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from uuid import uuid4

from app.models import AssetClass, OrderSide, OrderStatus, OrderType


DECIMAL_PLACES = Decimal("0.00000001")


def quantize_decimal(value: Decimal) -> Decimal:
    return value.quantize(DECIMAL_PLACES, rounding=ROUND_HALF_UP)


class BrokerError(Exception):
    """Base paper broker exception."""


class InsufficientFundsError(BrokerError):
    """Raised when cash is insufficient for an order."""


class InsufficientPositionError(BrokerError):
    """Raised when position inventory is insufficient for an order."""


class OrderNotFoundError(BrokerError):
    """Raised when an order id is unknown."""


class InvalidOrderError(BrokerError):
    """Raised when an order request is invalid."""


class FillReason(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


@dataclass(slots=True)
class OrderRequest:
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None


@dataclass(slots=True)
class BalanceSnapshot:
    currency: str
    total: Decimal
    available: Decimal
    reserved: Decimal
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class PositionSnapshot:
    symbol: str
    asset_class: AssetClass
    quantity: Decimal
    reserved_quantity: Decimal
    average_entry_price: Decimal
    market_price: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class OrderSnapshot:
    id: str
    symbol: str
    asset_class: AssetClass
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    status: OrderStatus
    created_at: datetime
    updated_at: datetime
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None
    reserved_cash: Decimal = Decimal("0")
    reserved_quantity: Decimal = Decimal("0")
    filled_quantity: Decimal = Decimal("0")
    average_fill_price: Decimal | None = None
    fee_paid: Decimal = Decimal("0")


@dataclass(slots=True)
class FillSnapshot:
    id: str
    order_id: str
    symbol: str
    asset_class: AssetClass
    side: OrderSide
    quantity: Decimal
    price: Decimal
    fee: Decimal
    reason: FillReason
    filled_at: datetime


@dataclass(slots=True)
class AccountSnapshot:
    asset_class: AssetClass
    base_currency: str
    cash_total: Decimal
    cash_available: Decimal
    cash_reserved: Decimal
    equity: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    open_order_count: int
    position_count: int
    updated_at: datetime


def build_order_id(asset_class: AssetClass) -> str:
    prefix = "stk" if asset_class is AssetClass.STOCK else "cry"
    return f"{prefix}_{uuid4().hex[:16]}"



def build_fill_id(asset_class: AssetClass) -> str:
    prefix = "fill_stk" if asset_class is AssetClass.STOCK else "fill_cry"
    return f"{prefix}_{uuid4().hex[:16]}"
