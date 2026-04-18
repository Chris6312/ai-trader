from __future__ import annotations

from dataclasses import dataclass
from typing import List

from sqlalchemy.orm import Session

from app.models.trading import Signal
from app.services.signal_service import SignalService
from app.strategies.momentum import MomentumStrategy
from app.strategies.trend_continuation import TrendContinuationStrategy
from app.strategies.types import StrategyInputBundle, StrategyResult


@dataclass
class StrategyEvaluationRecord:
    result: StrategyResult
    signal: Signal | None


class StrategyEngine:
    def __init__(self) -> None:
        self.strategies = [
            MomentumStrategy(),
            TrendContinuationStrategy(),
        ]

    def evaluate_symbol(
        self,
        db: Session,
        bundle: StrategyInputBundle,
    ) -> List[StrategyResult]:
        evaluation_records = self.evaluate_symbol_with_records(db=db, bundle=bundle)
        return [record.result for record in evaluation_records]

    def evaluate_symbol_with_records(
        self,
        db: Session,
        bundle: StrategyInputBundle,
    ) -> List[StrategyEvaluationRecord]:
        records: List[StrategyEvaluationRecord] = []

        for strategy in self.strategies:
            result = strategy.evaluate(bundle)
            persisted_signal: Signal | None = None

            if result.passed:
                persisted_signal = SignalService.create_signal(
                    db=db,
                    symbol=result.symbol,
                    asset_class=result.asset_class,
                    strategy=result.strategy,
                    timeframe=bundle.primary_timeframe,
                    confidence=result.confidence,
                    reasoning={
                        "summary": result.reasoning.summary,
                        "indicators": result.reasoning.indicators,
                        "checks": result.reasoning.checks,
                        "candles": [str(ts) for ts in result.reasoning.candle_timestamps],
                    },
                )

            records.append(StrategyEvaluationRecord(result=result, signal=persisted_signal))

        return records
