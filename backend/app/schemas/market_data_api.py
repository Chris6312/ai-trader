from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models import AssetClass, CandleInterval, MarketDataProvider


class CachedQuoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider: MarketDataProvider
    asset_class: AssetClass
    symbol: str
    bid: Decimal | None = None
    ask: Decimal | None = None
    last: Decimal
    mark: Decimal
    volume_24h: Decimal | None = None
    as_of: datetime


class MarketCandleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider: MarketDataProvider
    asset_class: AssetClass
    symbol: str
    interval: CandleInterval
    open_time: datetime
    close_time: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: Decimal
    vwap: Decimal | None = None
    trade_count: int | None = None
    is_closed: bool
    source_updated_at: datetime | None = None


class FetchAuditOut(BaseModel):
    worker_enabled: bool
    closed_candle_owner: str
    duplicate_fetch_paths_detected: bool
    quote_read_paths_allowed: bool
    notes: list[str]
