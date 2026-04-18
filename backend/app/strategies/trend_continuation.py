
from statistics import mean
from app.strategies.base import Strategy
from app.strategies.types import StrategyInputBundle, StrategyResult, StrategyReasoning

class TrendContinuationStrategy(Strategy):

    strategy_name = "trend_continuation"
    primary_timeframe = "15m"
    confirmation_timeframes = ["1h"]

    def evaluate(self, data: StrategyInputBundle) -> StrategyResult:

        closes = [c.close for c in data.candles]

        if len(closes) < 20:
            return StrategyResult(
                symbol=data.symbol,
                asset_class=data.asset_class,
                strategy=self.strategy_name,
                confidence=0.0,
                passed=False,
                reasoning=StrategyReasoning(
                    strategy=self.strategy_name,
                    summary="not enough candles",
                    indicators={},
                    checks={"min_candles": False},
                    candle_timestamps=[c.timestamp for c in data.candles],
                ),
            )

        ema_fast = mean(closes[-8:])
        ema_mid = mean(closes[-13:])
        ema_slow = mean(closes[-21:])

        trend_aligned = ema_fast > ema_mid > ema_slow
        price_position = closes[-1] > ema_fast

        confirmation_ok = True

        if data.confirmation and "1h" in data.confirmation:
            htf_closes = [c.close for c in data.confirmation["1h"]]

            if len(htf_closes) >= 21:
                htf_fast = mean(htf_closes[-8:])
                htf_mid = mean(htf_closes[-13:])
                htf_slow = mean(htf_closes[-21:])

                confirmation_ok = htf_fast > htf_mid > htf_slow

        passed = trend_aligned and price_position and confirmation_ok

        confidence = 0.5
        if passed:
            alignment_strength = (ema_fast - ema_slow) / ema_slow
            confidence = min(1.0, alignment_strength * 10)

        reasoning = StrategyReasoning(
            strategy=self.strategy_name,
            summary="trend continuation conditions met" if passed else "conditions not met",
            indicators={
                "ema_fast": ema_fast,
                "ema_mid": ema_mid,
                "ema_slow": ema_slow,
            },
            checks={
                "ema_stack": trend_aligned,
                "price_above_fast": price_position,
                "htf_confirmation": confirmation_ok,
            },
            candle_timestamps=[c.timestamp for c in data.candles],
        )

        return StrategyResult(
            symbol=data.symbol,
            asset_class=data.asset_class,
            strategy=self.strategy_name,
            confidence=confidence,
            passed=passed,
            reasoning=reasoning,
        )
