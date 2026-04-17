from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

from app.models import AssetClass, CandleInterval, MarketDataProvider


class NormalizedSymbolMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: MarketDataProvider
    asset_class: AssetClass
    symbol: str
    provider_symbol: str
    base_currency: str
    quote_currency: str
    tick_size: Decimal | None = None
    lot_size: Decimal | None = None
    is_active: bool = True
    last_synced_at: datetime | None = None


class NormalizedCandle(BaseModel):
    model_config = ConfigDict(frozen=True)

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
    is_closed: bool = True
    source_updated_at: datetime | None = None

    @field_validator("close_time")
    @classmethod
    def validate_close_time(cls, value: datetime, info) -> datetime:
        open_time = info.data.get("open_time")
        if open_time is not None and value <= open_time:
            raise ValueError("close_time must be after open_time")
        return value


class NormalizedQuote(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: MarketDataProvider
    asset_class: AssetClass
    symbol: str
    bid: Decimal | None = None
    ask: Decimal | None = None
    last: Decimal
    mark: Decimal
    volume_24h: Decimal | None = None
    as_of: datetime

    @field_validator("mark")
    @classmethod
    def default_mark_from_last(cls, value: Decimal, info) -> Decimal:
        return value if value is not None else info.data["last"]
