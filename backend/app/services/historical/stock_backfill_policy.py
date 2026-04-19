from __future__ import annotations

from app.services.historical.stock_backfill_policy_schemas import (
    StockBackfillPolicy,
    StockBackfillTimeframePolicy,
)


class StockBackfillPolicyService:
    POLICY_VERSION = "12q_stock_policy_v1"
    POLICY_NAME = "ml_stock_history_defaults"
    ASSET_CLASS = "stock"
    SYMBOL_SOURCE = "active_registry"
    MAX_SYMBOLS_PER_RUN = 200
    MAX_PARALLEL_FETCHES = 5
    DEFAULT_TIMEFRAME_LOOKBACKS: dict[str, tuple[int, str]] = {
        "15m": (60, "60 trading days"),
        "1h": (180, "6 months"),
        "4h": (365, "12 months"),
        "1d": (730, "2 years"),
    }

    def resolve_default_policy(self) -> StockBackfillPolicy:
        return StockBackfillPolicy(
            policy_version=self.POLICY_VERSION,
            policy_name=self.POLICY_NAME,
            asset_class=self.ASSET_CLASS,
            symbol_source=self.SYMBOL_SOURCE,
            max_symbols_per_run=self.MAX_SYMBOLS_PER_RUN,
            max_parallel_fetches=self.MAX_PARALLEL_FETCHES,
            timeframes={
                timeframe: StockBackfillTimeframePolicy(
                    timeframe=timeframe,
                    lookback_days=lookback_days,
                    lookback_label=lookback_label,
                )
                for timeframe, (lookback_days, lookback_label) in self.DEFAULT_TIMEFRAME_LOOKBACKS.items()
            },
        )

    def resolve_lookback_days(self, timeframe: str) -> int:
        try:
            lookback_days, _ = self.DEFAULT_TIMEFRAME_LOOKBACKS[timeframe]
        except KeyError as exc:
            raise ValueError(f"Unsupported stock backfill timeframe: {timeframe}") from exc
        return lookback_days
