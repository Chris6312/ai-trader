from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from app.models.trading import AssetClass


@dataclass(slots=True)
class HistoricalLabelPolicy:
    label_version: str
    policy_name: str
    success_threshold_return: Decimal
    max_drawdown_return: Decimal
    require_target_before_stop: bool
    max_hold_bars: int


@dataclass(slots=True)
class LabelPolicyVersionRecord:
    label_version: str
    policy_name: str
    success_threshold_return: Decimal
    max_drawdown_return: Decimal
    require_target_before_stop: bool
    max_hold_bars: int
    created_at: datetime


@dataclass(slots=True)
class HistoricalReplayLabelRecord:
    decision_date: date
    symbol: str
    asset_class: AssetClass
    timeframe: str
    strategy_name: str
    entry_candle_time: datetime
    source_label: str
    replay_version: str
    label_version: str
    is_trade_profitable: bool
    hit_target_before_stop: bool
    follow_through_strength: Decimal
    drawdown_within_limit: bool
    achieved_label: bool
    label_values: dict[str, object]


@dataclass(slots=True)
class HistoricalLabelGenerationSummary:
    decision_date: date
    asset_class: AssetClass
    timeframe: str
    label_version: str
    replay_version: str | None
    rows_considered: int
    rows_labeled: int
    rows_replaced: int
