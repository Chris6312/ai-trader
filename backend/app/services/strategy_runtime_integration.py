
from app.services.strategy_engine import StrategyEngine

engine = StrategyEngine()

def evaluate_from_candles(db, bundle):

    return engine.evaluate_symbol(
        db=db,
        bundle=bundle
    )
