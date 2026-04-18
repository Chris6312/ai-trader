
from typing import List
from sqlalchemy.orm import Session

from app.strategies.momentum import MomentumStrategy
from app.strategies.trend_continuation import TrendContinuationStrategy
from app.strategies.types import StrategyInputBundle, StrategyResult

from app.services.signal_service import SignalService


class StrategyEngine:

    def __init__(self):
        self.strategies = [
            MomentumStrategy(),
            TrendContinuationStrategy(),
        ]

    def evaluate_symbol(
        self,
        db: Session,
        bundle: StrategyInputBundle
    ) -> List[StrategyResult]:

        results: List[StrategyResult] = []

        for strategy in self.strategies:

            result = strategy.evaluate(bundle)

            if result.passed:

                SignalService.create_signal(
                    db=db,
                    symbol=result.symbol,
                    asset_class=result.asset_class,
                    strategy=result.strategy,
                    confidence=result.confidence,
                    reasoning={
                        "summary": result.reasoning.summary,
                        "indicators": result.reasoning.indicators,
                        "checks": result.reasoning.checks,
                        "candles": [
                            str(ts) for ts in result.reasoning.candle_timestamps
                        ],
                    },
                )

            results.append(result)

        return results
