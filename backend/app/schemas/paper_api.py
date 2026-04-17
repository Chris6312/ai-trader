from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models import AssetClass, OrderSide, OrderStatus, OrderType


class BalanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    currency: str
    total: Decimal
    available: Decimal
    reserved: Decimal
    updated_at: datetime


class PositionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str
    asset_class: AssetClass
    quantity: Decimal
    reserved_quantity: Decimal
    average_entry_price: Decimal
    market_price: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    updated_at: datetime


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
    reserved_cash: Decimal
    reserved_quantity: Decimal
    filled_quantity: Decimal
    average_fill_price: Decimal | None = None
    fee_paid: Decimal


class AccountSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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


class ResetBalanceRequest(BaseModel):
    amount: Decimal = Field(gt=0)
