from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(slots=True)
class HistoricalBacktestingPolicy:
    policy_version: str
    policy_name: str
    replay_policy_version: str
    label_version: str
    evaluation_window_bars: int
    success_threshold_return: Decimal
    max_drawdown_return: Decimal
    require_target_before_stop: bool
    regime_adjustments: dict[str, object]


@dataclass(slots=True)
class BacktestingPolicyVersionRecord:
    policy_version: str
    policy_name: str
    replay_policy_version: str
    label_version: str
    evaluation_window_bars: int
    success_threshold_return: Decimal
    max_drawdown_return: Decimal
    require_target_before_stop: bool
    regime_adjustments: dict[str, object]
    created_at: datetime


@dataclass(slots=True)
class ResolvedBacktestingPolicyRecord:
    policy_version: str
    replay_policy_version: str
    label_version: str
    evaluation_window_bars: int
    success_threshold_return: Decimal
    max_drawdown_return: Decimal
    require_target_before_stop: bool
    regime_adjustments: dict[str, object]
