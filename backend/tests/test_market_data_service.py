from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.market_data.schemas import NormalizedCandle, NormalizedQuote, NormalizedSymbolMetadata
from app.models import AssetClass, CandleInterval, MarketCandle, MarketDataProvider, SymbolMetadata
from app.services.market_data import MarketDataService


class FakeRedis:
    def __init__(self) -> None:
        self.storage: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.storage[key] = value
        if ex is not None:
            self.ttls[key] = ex

    def get(self, key: str) -> str | None:
        return self.storage.get(key)


def _build_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def test_market_data_service_upserts_symbol_metadata_and_candles() -> None:
    db = _build_session()
    service = MarketDataService()

    synced_at = datetime(2026, 4, 17, 22, 0, tzinfo=UTC)
    service.upsert_symbol_metadata(
        db,
        NormalizedSymbolMetadata(
            provider=MarketDataProvider.KRAKEN,
            asset_class=AssetClass.CRYPTO,
            symbol="BTC/USD",
            provider_symbol="XBTUSD",
            base_currency="BTC",
            quote_currency="USD",
            tick_size=Decimal("0.1"),
            lot_size=Decimal("8"),
            last_synced_at=synced_at,
        ),
    )
    inserted_count = service.upsert_candles(
        db,
        [
            NormalizedCandle(
                provider=MarketDataProvider.KRAKEN,
                asset_class=AssetClass.CRYPTO,
                symbol="BTC/USD",
                interval=CandleInterval.HOUR_1,
                open_time=datetime(2026, 4, 17, 21, 0, tzinfo=UTC),
                close_time=datetime(2026, 4, 17, 22, 0, tzinfo=UTC),
                open_price=Decimal("64000"),
                high_price=Decimal("64100"),
                low_price=Decimal("63900"),
                close_price=Decimal("64050"),
                volume=Decimal("12.5"),
                vwap=Decimal("64010"),
                trade_count=42,
            )
        ],
    )
    updated_count = service.upsert_candles(
        db,
        [
            NormalizedCandle(
                provider=MarketDataProvider.KRAKEN,
                asset_class=AssetClass.CRYPTO,
                symbol="BTC/USD",
                interval=CandleInterval.HOUR_1,
                open_time=datetime(2026, 4, 17, 21, 0, tzinfo=UTC),
                close_time=datetime(2026, 4, 17, 22, 0, tzinfo=UTC),
                open_price=Decimal("64000"),
                high_price=Decimal("64200"),
                low_price=Decimal("63900"),
                close_price=Decimal("64150"),
                volume=Decimal("18.5"),
                vwap=Decimal("64080"),
                trade_count=48,
            )
        ],
    )
    db.commit()

    metadata = db.scalar(select(SymbolMetadata))
    candle = db.scalar(select(MarketCandle))

    assert inserted_count == 1
    assert updated_count == 1
    assert metadata is not None
    assert metadata.provider_symbol == "XBTUSD"
    assert candle is not None
    assert str(candle.close_price) == "64150.00000000"
    assert candle.trade_count == 48


def test_market_data_service_caches_quotes_in_redis_shape() -> None:
    redis_client = FakeRedis()
    service = MarketDataService(redis_client=redis_client)
    quote = NormalizedQuote(
        provider=MarketDataProvider.TRADIER,
        asset_class=AssetClass.STOCK,
        symbol="AAPL",
        bid=Decimal("189.2"),
        ask=Decimal("189.4"),
        last=Decimal("189.3"),
        mark=Decimal("189.3"),
        volume_24h=Decimal("3456789"),
        as_of=datetime(2026, 4, 17, 21, 35, tzinfo=UTC),
    )

    service.cache_quote(quote, ttl_seconds=45)
    cached_quote = service.get_cached_quote("tradier", "AAPL")

    assert cached_quote is not None
    assert cached_quote.provider == MarketDataProvider.TRADIER
    assert cached_quote.symbol == "AAPL"
    assert str(cached_quote.last) == "189.3"
    assert redis_client.ttls["market_quote:tradier:AAPL"] == 45
