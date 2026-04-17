from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.market_data.kraken import KrakenMarketDataAdapter
from app.market_data.tradier import TradierMarketDataAdapter
from app.models import CandleInterval, MarketDataProvider, SymbolMetadata
from app.services.market_data import MarketDataService


@dataclass(frozen=True)
class CandleSyncResult:
    interval: CandleInterval
    stored: int
    skipped: int


class MarketDataRuntimeService:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        market_data_service: MarketDataService,
        kraken_adapter: KrakenMarketDataAdapter | None = None,
        tradier_adapter: TradierMarketDataAdapter | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.market_data_service = market_data_service
        self.kraken_adapter = kraken_adapter or KrakenMarketDataAdapter()
        self.tradier_adapter = tradier_adapter or TradierMarketDataAdapter()

    async def sync_quotes(
        self,
        *,
        crypto_symbols: Sequence[str],
        stock_symbols: Sequence[str],
    ) -> int:
        cached_count = 0

        if crypto_symbols:
            await self.sync_kraken_symbol_metadata(crypto_symbols)

        for symbol in stock_symbols:
            quote = await self.tradier_adapter.fetch_quote(symbol)
            self.market_data_service.cache_quote(quote)
            cached_count += 1

        if crypto_symbols:
            with self.session_factory() as db:
                for symbol in crypto_symbols:
                    provider_symbol = self._provider_symbol_for(db, MarketDataProvider.KRAKEN, symbol)
                    if provider_symbol is None:
                        continue
                    quote = await self.kraken_adapter.fetch_ticker(provider_symbol)
                    self.market_data_service.cache_quote(quote)
                    cached_count += 1

        return cached_count

    async def sync_closed_candles(
        self,
        *,
        crypto_symbols: Sequence[str],
        stock_symbols: Sequence[str],
        interval: CandleInterval,
        as_of: datetime | None = None,
    ) -> CandleSyncResult:
        as_of = as_of or datetime.now(UTC)
        stored = 0
        skipped = 0

        if crypto_symbols:
            await self.sync_kraken_symbol_metadata(crypto_symbols)

        with self.session_factory() as db:
            for symbol in crypto_symbols:
                provider_symbol = self._provider_symbol_for(db, MarketDataProvider.KRAKEN, symbol)
                if provider_symbol is None:
                    skipped += 1
                    continue

                candles = await self.kraken_adapter.fetch_ohlc(provider_symbol, interval)
                latest_closed = self._latest_closed_only(candles, as_of=as_of)
                if not latest_closed:
                    skipped += 1
                    continue

                stored += self.market_data_service.upsert_candles(db, latest_closed)

            if interval == CandleInterval.DAY_1:
                for symbol in stock_symbols:
                    candles = await self.tradier_adapter.fetch_history(symbol, interval)
                    latest_closed = self._latest_closed_only(candles, as_of=as_of)
                    if not latest_closed:
                        skipped += 1
                        continue

                    stored += self.market_data_service.upsert_candles(db, latest_closed)
            else:
                skipped += len(stock_symbols)

            db.commit()

        return CandleSyncResult(interval=interval, stored=stored, skipped=skipped)

    async def sync_kraken_symbol_metadata(self, symbols: Sequence[str]) -> int:
        available_pairs = await self.kraken_adapter.fetch_asset_pairs()
        by_symbol = {item.symbol: item for item in available_pairs}
        upserted = 0

        with self.session_factory() as db:
            for symbol in symbols:
                metadata = by_symbol.get(symbol)
                if metadata is None:
                    continue
                self.market_data_service.upsert_symbol_metadata(db, metadata)
                upserted += 1
            db.commit()

        return upserted

    def _provider_symbol_for(
        self,
        db: Session,
        provider: MarketDataProvider,
        symbol: str,
    ) -> str | None:
        row = db.scalar(
            select(SymbolMetadata).where(
                SymbolMetadata.provider == provider,
                SymbolMetadata.symbol == symbol,
            )
        )
        return row.provider_symbol if row is not None else None

    def _latest_closed_only(self, candles: Sequence[object], *, as_of: datetime) -> list[object]:
        eligible = [
            candle
            for candle in candles
            if getattr(candle, "is_closed", False) and getattr(candle, "close_time", as_of) <= as_of
        ]
        if not eligible:
            return []
        latest = max(eligible, key=lambda candle: getattr(candle, "open_time"))
        return [latest]
