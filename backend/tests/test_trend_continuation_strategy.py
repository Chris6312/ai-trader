
from datetime import datetime, UTC
from app.strategies.trend_continuation import TrendContinuationStrategy
from app.strategies.types import Candle, StrategyInputBundle

def test_trend_alignment():

    candles = [
        Candle(datetime.now(UTC),1,1,1,1+i*0.05,100)
        for i in range(30)
    ]

    htf_candles = [
        Candle(datetime.now(UTC),1,1,1,1+i*0.1,100)
        for i in range(30)
    ]

    strategy = TrendContinuationStrategy()

    result = strategy.evaluate(
        StrategyInputBundle(
            symbol="TEST",
            asset_class="crypto",
            primary_timeframe="15m",
            candles=candles,
            confirmation={"1h": htf_candles},
        )
    )

    assert result.strategy == "trend_continuation"
    assert isinstance(result.passed, bool)
    assert "ema_fast" in result.reasoning.indicators
