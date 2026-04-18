
from statistics import mean
from app.strategies.base import Strategy
from app.strategies.types import StrategyInputBundle, StrategyResult, StrategyReasoning

class MomentumStrategy(Strategy):

    strategy_name = "momentum"
    primary_timeframe = "15m"
    confirmation_timeframes = None

    def evaluate(self, data: StrategyInputBundle) -> StrategyResult:

        closes = [c.close for c in data.candles]
        volumes = [c.volume for c in data.candles]

        if len(closes) < 10:
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

        ema_fast = mean(closes[-5:])
        ema_slow = mean(closes[-10:])

        momentum = (closes[-1] - closes[-5]) / closes[-5]

        avg_volume = mean(volumes[-10:])
        volume_ratio = volumes[-1] / avg_volume if avg_volume else 0

        passed = (
            ema_fast > ema_slow
            and closes[-1] > ema_fast
            and momentum > 0
            and volume_ratio > 1
        )

        confidence = min(1.0, max(0.0, momentum * 5))

        reasoning = StrategyReasoning(
            strategy=self.strategy_name,
            summary="momentum conditions met" if passed else "conditions not met",
            indicators={
                "ema_fast": ema_fast,
                "ema_slow": ema_slow,
                "momentum": momentum,
                "volume_ratio": volume_ratio,
            },
            checks={
                "ema_alignment": ema_fast > ema_slow,
                "price_above_fast": closes[-1] > ema_fast,
                "momentum_positive": momentum > 0,
                "volume_expansion": volume_ratio > 1,
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
