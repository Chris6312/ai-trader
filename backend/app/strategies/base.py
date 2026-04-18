
from abc import ABC, abstractmethod
from .types import StrategyInputBundle, StrategyResult

class Strategy(ABC):
    strategy_name: str
    primary_timeframe: str
    confirmation_timeframes: list[str] | None = None

    @abstractmethod
    def evaluate(self, data: StrategyInputBundle) -> StrategyResult:
        ...
