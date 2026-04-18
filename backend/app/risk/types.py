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


class RiskApprovalRejection(str, Enum):
    MAX_OPEN_POSITIONS_EXCEEDED = "max_open_positions_exceeded"
    TOTAL_EXPOSURE_CAP_EXCEEDED = "total_exposure_cap_exceeded"
    SYMBOL_EXPOSURE_CAP_EXCEEDED = "symbol_exposure_cap_exceeded"
    DAILY_LOSS_LIMIT_REACHED = "daily_loss_limit_reached"
    STALE_QUOTE = "stale_quote"
    INVALID_QUOTE = "invalid_quote"
    SPREAD_TOO_WIDE = "spread_too_wide"


@dataclass(slots=True)
class OpenPositionSnapshot:
    symbol: str
    asset_class: str
    notional_value: Decimal


@dataclass(slots=True)
class RiskApprovalInput:
    symbol: str
    asset_class: str
    account_equity: Decimal
    proposed_notional_value: Decimal
    proposed_risk_amount: Decimal
    quote_bid: Decimal
    quote_ask: Decimal
    quote_age_seconds: int
    open_positions: list[OpenPositionSnapshot]
    max_open_positions: int
    max_total_exposure_percent: Decimal
    max_symbol_exposure_percent: Decimal
    max_daily_loss_percent: Decimal
    realized_pnl_today: Decimal = Decimal("0")
    max_quote_age_seconds: int = 60
    max_spread_percent: Decimal = Decimal("1")


@dataclass(slots=True)
class RiskApprovalReasoning:
    summary: str
    checks: dict[str, bool]
    inputs: dict[str, str]
    computed: dict[str, str]
    rejection_path: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RiskApprovalResult:
    symbol: str
    asset_class: str
    approved: bool
    rejection_reason: RiskApprovalRejection | None
    reasoning: RiskApprovalReasoning
