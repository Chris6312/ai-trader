
from app.strategies.types import StrategyReasoning

def test_reasoning_shape():
    r = StrategyReasoning(
        strategy="momentum",
        summary="ok",
        indicators={},
        checks={},
        candle_timestamps=[]
    )

    assert r.strategy == "momentum"
