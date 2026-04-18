from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum


class PositionSizingRejection(str, Enum):
    INVALID_ENTRY_PRICE = "invalid_entry_price"
    INVALID_ATR = "invalid_atr"
    INVALID_STOP_MULTIPLE = "invalid_stop_multiple"
    INVALID_RISK_PERCENT = "invalid_risk_percent"
    ZERO_RISK_BUDGET = "zero_risk_budget"
    ZERO_QUANTITY = "zero_quantity"


@dataclass(slots=True)
class PositionSizingInput:
    symbol: str
    asset_class: str
    entry_price: Decimal
    atr: Decimal
    stop_atr_multiple: Decimal
    account_equity: Decimal
    available_cash: Decimal
    risk_percent: Decimal
    max_position_notional_percent: Decimal | None = None
    fee_buffer_percent: Decimal = Decimal("0")


@dataclass(slots=True)
class PositionSizingReasoning:
    summary: str
    checks: dict[str, bool]
    inputs: dict[str, str]
    computed: dict[str, str]
    caps_applied: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PositionSizingResult:
    symbol: str
    asset_class: str
    quantity: Decimal
    stop_price: Decimal
    risk_amount: Decimal
    risk_per_unit: Decimal
    notional_value: Decimal
    rejected: bool
    rejection_reason: PositionSizingRejection | None
    reasoning: PositionSizingReasoning
