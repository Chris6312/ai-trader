from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from app.models.trading import AssetClass


@dataclass(slots=True)
class HistoricalReplayPolicy:
    policy_version: str
    max_hold_bars: int
    target_r_multiple: Decimal
    supported_strategies: tuple[str, ...]


@dataclass(slots=True)
class HistoricalReplayCandidate:
    symbol: str
    asset_class: AssetClass
    timeframe: str
    decision_date: date
    entry_candle_time: datetime
    entry_price: Decimal
    stop_price: Decimal
    target_price: Decimal
    strategy_result: object
    risk_result: object
    source_label: str
    replay_version: str
    policy_version: str


@dataclass(slots=True)
class HistoricalReplayRecord:
    decision_date: date
    symbol: str
    asset_class: AssetClass
    timeframe: str
    strategy_name: str
    source_label: str
    replay_version: str
    policy_version: str
    entry_candle_time: datetime
    exit_candle_time: datetime
    entry_price: Decimal
    exit_price: Decimal
    stop_price: Decimal
    target_price: Decimal
    entry_confidence: Decimal
    risk_approved: bool
    exit_reason: str
    hold_bars: int
    max_favorable_excursion: Decimal
    max_adverse_excursion: Decimal
    gross_return: Decimal
    strategy_summary: str
    strategy_checks: dict[str, object]
    strategy_indicators: dict[str, object]
    risk_rejection_reason: str | None


@dataclass(slots=True)
class HistoricalReplaySummary:
    decision_date: date
    asset_class: str
    timeframe: str
    source_label: str
    replay_version: str
    policy_version: str
    symbols_requested: int
    entries_evaluated: int
    entries_approved: int
    trades_persisted: int
    rows_replaced: int
