from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class StockBackfillTimeframePolicy:
    timeframe: str
    lookback_days: int
    lookback_label: str


@dataclass(slots=True)
class StockBackfillPolicy:
    policy_version: str
    policy_name: str
    asset_class: str
    symbol_source: str
    max_symbols_per_run: int
    max_parallel_fetches: int
    timeframes: dict[str, StockBackfillTimeframePolicy] = field(default_factory=dict)
