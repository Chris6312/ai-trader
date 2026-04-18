
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

@dataclass
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

@dataclass
class StrategyInputBundle:
    symbol: str
    asset_class: str
    primary_timeframe: str
    candles: List[Candle]
    confirmation: Optional[Dict[str, List[Candle]]] = None

@dataclass
class StrategyReasoning:
    strategy: str
    summary: str
    indicators: Dict
    checks: Dict
    candle_timestamps: List[datetime]

@dataclass
class StrategyResult:
    symbol: str
    asset_class: str
    strategy: str
    confidence: float
    passed: bool
    reasoning: StrategyReasoning
