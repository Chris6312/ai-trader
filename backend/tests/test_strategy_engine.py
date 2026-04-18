
from datetime import datetime, UTC

from app.strategies.types import Candle, StrategyInputBundle
from app.services.strategy_engine import StrategyEngine


class DummyDB:
    def add(self, *a, **kw): pass
    def commit(self): pass
    def refresh(self, *a, **kw): pass


def test_engine_runs():

    candles = [
        Candle(datetime.now(UTC),1,1,1,1+i*0.05,100+i)
        for i in range(40)
    ]

    bundle = StrategyInputBundle(
        symbol="TEST",
        asset_class="crypto",
        primary_timeframe="15m",
        candles=candles,
        confirmation={"1h": candles},
    )

    engine = StrategyEngine()

    results = engine.evaluate_symbol(
        db=DummyDB(),
        bundle=bundle,
    )

    assert len(results) >= 1
