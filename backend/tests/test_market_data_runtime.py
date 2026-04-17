from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.market_data.schemas import NormalizedCandle, NormalizedQuote, NormalizedSymbolMetadata
from app.models import AssetClass, CandleInterval, MarketCandle, MarketDataProvider, SymbolMetadata
from app.services.market_data import MarketDataService
from app.services.market_data_runtime import MarketDataRuntimeService


class FakeRedis:
    def __init__(self) -> None:
        self.storage: dict[str, str] = {}

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.storage[key] = value

    def get(self, key: str) -> str | None:
        return self.storage.get(key)


class FakeKrakenAdapter:
    async def fetch_asset_pairs(self):
        return [
            NormalizedSymbolMetadata(
                provider=MarketDataProvider.KRAKEN,
                asset_class=AssetClass.CRYPTO,
                symbol="BTC/USD",
                provider_symbol="XBTUSD",
                base_currency="BTC",
                quote_currency="USD",
                tick_size=Decimal("0.1"),
                lot_size=Decimal("0.0001"),
                last_synced_at=datetime(2026, 4, 17, 21, 0, tzinfo=UTC),
            )
        ]

    async def fetch_ticker(self, provider_symbol: str):
        assert provider_symbol == "XBTUSD"
        return NormalizedQuote(
            provider=MarketDataProvider.KRAKEN,
            asset_class=AssetClass.CRYPTO,
            symbol="BTC/USD",
            bid=Decimal("64000"),
            ask=Decimal("64010"),
            last=Decimal("64005"),
            mark=Decimal("64005"),
            volume_24h=Decimal("100"),
            as_of=datetime(2026, 4, 17, 21, 5, tzinfo=UTC),
        )

    async def fetch_ohlc(self, provider_symbol: str, interval: CandleInterval):
        assert provider_symbol == "XBTUSD"

        if interval == CandleInterval.MINUTE_5:
            return [
                NormalizedCandle(
                    provider=MarketDataProvider.KRAKEN,
                    asset_class=AssetClass.CRYPTO,
                    symbol="BTC/USD",
                    interval=CandleInterval.MINUTE_5,
                    open_time=datetime(2026, 4, 17, 21, 0, tzinfo=UTC),
                    close_time=datetime(2026, 4, 17, 21, 5, tzinfo=UTC),
                    open_price=Decimal("63950"),
                    high_price=Decimal("64025"),
                    low_price=Decimal("63900"),
                    close_price=Decimal("64005"),
                    volume=Decimal("10"),
                    vwap=Decimal("63990"),
                    trade_count=42,
                    is_closed=True,
                    source_updated_at=datetime(2026, 4, 17, 21, 5, tzinfo=UTC),
                )
            ]

        if interval == CandleInterval.DAY_1:
            return [
                NormalizedCandle(
                    provider=MarketDataProvider.KRAKEN,
                    asset_class=AssetClass.CRYPTO,
                    symbol="BTC/USD",
                    interval=CandleInterval.DAY_1,
                    open_time=datetime(2026, 4, 16, 0, 0, tzinfo=UTC),
                    close_time=datetime(2026, 4, 16, 23, 59, 59, tzinfo=UTC),
                    open_price=Decimal("63000"),
                    high_price=Decimal("64500"),
                    low_price=Decimal("62800"),
                    close_price=Decimal("64005"),
                    volume=Decimal("250"),
                    vwap=Decimal("63750"),
                    trade_count=420,
                    is_closed=True,
                    source_updated_at=datetime(2026, 4, 16, 23, 59, 59, tzinfo=UTC),
                )
            ]

        raise AssertionError(f"Unexpected interval: {interval}")


class FakeTradierAdapter:
    is_configured = True

    def __init__(self) -> None:
        self.history_calls: list[tuple[str, CandleInterval]] = []

    async def fetch_quote(self, symbol: str):
        assert symbol == "AAPL"
        return NormalizedQuote(
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

    async def fetch_history(self, symbol: str, interval: CandleInterval):
        self.history_calls.append((symbol, interval))
        assert symbol == "AAPL"
        return [
            NormalizedCandle(
                provider=MarketDataProvider.TRADIER,
                asset_class=AssetClass.STOCK,
                symbol="AAPL",
                interval=interval,
                open_time=datetime(2026, 4, 16, 0, 0, tzinfo=UTC),
                close_time=datetime(2026, 4, 16, 23, 59, 59, tzinfo=UTC),
                open_price=Decimal("187.2"),
                high_price=Decimal("190.0"),
                low_price=Decimal("186.5"),
                close_price=Decimal("189.3"),
                volume=Decimal("1234567"),
                vwap=None,
                trade_count=None,
                is_closed=True,
                source_updated_at=datetime(2026, 4, 16, 23, 59, 59, tzinfo=UTC),
            )
        ]


class FakeUnconfiguredTradierAdapter(FakeTradierAdapter):
    is_configured = False

    async def fetch_quote(self, symbol: str):
        raise AssertionError("fetch_quote should not be called when Tradier is unconfigured")

    async def fetch_history(self, symbol: str, interval: CandleInterval):
        raise AssertionError("fetch_history should not be called when Tradier is unconfigured")


def _build_session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return maker


@pytest.mark.asyncio
async def test_runtime_service_syncs_quotes_and_closed_candles_after_close() -> None:
    session_factory = _build_session_factory()
    service = MarketDataService(redis_client=FakeRedis())
    tradier = FakeTradierAdapter()
    runtime = MarketDataRuntimeService(
        session_factory=session_factory,
        market_data_service=service,
        kraken_adapter=FakeKrakenAdapter(),
        tradier_adapter=tradier,
    )

    quotes_cached = await runtime.sync_quotes(
        crypto_symbols=("BTC/USD",),
        stock_symbols=("AAPL",),
    )
    result = await runtime.sync_closed_candles(
        crypto_symbols=("BTC/USD",),
        stock_symbols=("AAPL",),
        interval=CandleInterval.DAY_1,
        as_of=datetime(2026, 4, 17, 20, 10, tzinfo=UTC),
    )
    crypto_only = await runtime.sync_closed_candles(
        crypto_symbols=("BTC/USD",),
        stock_symbols=("AAPL",),
        interval=CandleInterval.MINUTE_5,
        as_of=datetime(2026, 4, 17, 21, 10, tzinfo=UTC),
    )

    with session_factory() as db:
        metadata = db.scalar(select(SymbolMetadata).where(SymbolMetadata.symbol == "BTC/USD"))
        candles = db.scalars(select(MarketCandle)).all()

    assert quotes_cached == 2
    assert metadata is not None
    assert metadata.provider_symbol == "XBTUSD"
    assert result.stored == 2
    assert result.skipped == 0
    assert crypto_only.stored == 1
    assert crypto_only.skipped == 1
    assert len(candles) == 3
    assert tradier.history_calls == [("AAPL", CandleInterval.DAY_1)]


@pytest.mark.asyncio
async def test_runtime_service_skips_stock_fetches_before_close_without_backfill() -> None:
    session_factory = _build_session_factory()
    service = MarketDataService(redis_client=FakeRedis())
    tradier = FakeTradierAdapter()
    runtime = MarketDataRuntimeService(
        session_factory=session_factory,
        market_data_service=service,
        kraken_adapter=FakeKrakenAdapter(),
        tradier_adapter=tradier,
    )

    result = await runtime.sync_closed_candles(
        crypto_symbols=("BTC/USD",),
        stock_symbols=("AAPL",),
        interval=CandleInterval.DAY_1,
        as_of=datetime(2026, 4, 17, 19, 55, tzinfo=UTC),
        backfill=False,
    )

    with session_factory() as db:
        candles = db.scalars(select(MarketCandle)).all()

    assert result.stored == 1
    assert result.skipped == 1
    assert len(candles) == 1
    assert tradier.history_calls == []


@pytest.mark.asyncio
async def test_runtime_service_allows_backfill_before_close() -> None:
    session_factory = _build_session_factory()
    service = MarketDataService(redis_client=FakeRedis())
    tradier = FakeTradierAdapter()
    runtime = MarketDataRuntimeService(
        session_factory=session_factory,
        market_data_service=service,
        kraken_adapter=FakeKrakenAdapter(),
        tradier_adapter=tradier,
    )

    result = await runtime.sync_closed_candles(
        crypto_symbols=("BTC/USD",),
        stock_symbols=("AAPL",),
        interval=CandleInterval.DAY_1,
        as_of=datetime(2026, 4, 17, 19, 55, tzinfo=UTC),
        backfill=True,
    )

    assert result.stored == 2
    assert result.skipped == 0
    assert tradier.history_calls == [("AAPL", CandleInterval.DAY_1)]


@pytest.mark.asyncio
async def test_runtime_service_skips_stock_fetches_when_tradier_is_unconfigured() -> None:
    session_factory = _build_session_factory()
    service = MarketDataService(redis_client=FakeRedis())
    runtime = MarketDataRuntimeService(
        session_factory=session_factory,
        market_data_service=service,
        kraken_adapter=FakeKrakenAdapter(),
        tradier_adapter=FakeUnconfiguredTradierAdapter(),
    )

    quotes_cached = await runtime.sync_quotes(
        crypto_symbols=("BTC/USD",),
        stock_symbols=("AAPL",),
    )
    result = await runtime.sync_closed_candles(
        crypto_symbols=("BTC/USD",),
        stock_symbols=("AAPL",),
        interval=CandleInterval.DAY_1,
        as_of=datetime(2026, 4, 17, 21, 10, tzinfo=UTC),
    )

    readiness = runtime.get_provider_readiness()

    with session_factory() as db:
        candles = db.scalars(select(MarketCandle)).all()

    assert quotes_cached == 1
    assert result.stored == 1
    assert result.skipped == 1
    assert readiness["tradier"]["configured"] is False
    assert len(candles) == 1
