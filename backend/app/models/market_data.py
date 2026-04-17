from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import Boolean, DateTime, Enum as SqlEnum, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.trading import AssetClass


class MarketDataProvider(str, Enum):
    KRAKEN = "kraken"
    TRADIER = "tradier"


class CandleInterval(str, Enum):
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    HOUR_1 = "1h"
    HOUR_4 = "4h"
    DAY_1 = "1d"


class SymbolMetadata(Base):
    __tablename__ = "symbol_metadata"
    __table_args__ = (
        UniqueConstraint("provider", "symbol", name="uq_symbol_metadata_provider_symbol"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[MarketDataProvider] = mapped_column(
        SqlEnum(MarketDataProvider, name="market_data_provider_enum"),
        nullable=False,
        index=True,
    )
    asset_class: Mapped[AssetClass] = mapped_column(
        SqlEnum(AssetClass, name="market_data_asset_class_enum"),
        nullable=False,
        index=True,
    )
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    provider_symbol: Mapped[str] = mapped_column(String(80), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(20), nullable=False)
    quote_currency: Mapped[str] = mapped_column(String(20), nullable=False)
    tick_size: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    lot_size: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class MarketCandle(Base):
    __tablename__ = "market_candles"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "symbol",
            "interval",
            "open_time",
            name="uq_market_candles_provider_symbol_interval_open_time",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[MarketDataProvider] = mapped_column(
        SqlEnum(MarketDataProvider, name="market_data_provider_enum"),
        nullable=False,
        index=True,
    )
    asset_class: Mapped[AssetClass] = mapped_column(
        SqlEnum(AssetClass, name="market_data_asset_class_enum"),
        nullable=False,
        index=True,
    )
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    interval: Mapped[CandleInterval] = mapped_column(
        SqlEnum(CandleInterval, name="candle_interval_enum"),
        nullable=False,
        index=True,
    )
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    close_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open_price: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    high_price: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    low_price: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    close_price: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    volume: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False, default=Decimal("0"))
    vwap: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    trade_count: Mapped[int | None] = mapped_column(nullable=True)
    is_closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
