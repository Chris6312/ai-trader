from __future__ import annotations

from pydantic import BaseModel


class StockBackfillTimeframePolicyOut(BaseModel):
    timeframe: str
    lookback_days: int
    lookback_label: str


class StockBackfillPolicyOut(BaseModel):
    policy_version: str
    policy_name: str
    asset_class: str
    symbol_source: str
    max_symbols_per_run: int
    max_parallel_fetches: int
    timeframes: dict[str, StockBackfillTimeframePolicyOut]
