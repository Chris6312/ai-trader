
from datetime import datetime
from app.strategies.momentum import MomentumStrategy
from app.strategies.types import Candle, StrategyInputBundle

def test_momentum_positive():

    candles = [
        Candle(datetime.utcnow(),1,1,1,1+i*0.1,100+i*10)
        for i in range(12)
    ]

    strategy = MomentumStrategy()

    result = strategy.evaluate(
        StrategyInputBundle(
            symbol="TEST",
            asset_class="crypto",
            primary_timeframe="15m",
            candles=candles,
        )
    )

    assert result.strategy == "momentum"
    assert isinstance(result.passed, bool)
    assert "ema_fast" in result.reasoning.indicators
