from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.market_data.schemas import NormalizedCandle, NormalizedQuote, NormalizedSymbolMetadata
from app.models import MarketCandle, SymbolMetadata


class MarketDataService:
    def __init__(self, redis_client: object | None = None) -> None:
        self.redis_client = redis_client

    def upsert_symbol_metadata(self, db: Session, metadata: NormalizedSymbolMetadata) -> SymbolMetadata:
        existing = db.scalar(
            select(SymbolMetadata).where(
                SymbolMetadata.provider == metadata.provider,
                SymbolMetadata.symbol == metadata.symbol,
            )
        )
        if existing is None:
            existing = SymbolMetadata(
                provider=metadata.provider,
                asset_class=metadata.asset_class,
                symbol=metadata.symbol,
                provider_symbol=metadata.provider_symbol,
                base_currency=metadata.base_currency,
                quote_currency=metadata.quote_currency,
            )
            db.add(existing)

        existing.provider_symbol = metadata.provider_symbol
        existing.base_currency = metadata.base_currency
        existing.quote_currency = metadata.quote_currency
        existing.tick_size = metadata.tick_size
        existing.lot_size = metadata.lot_size
        existing.is_active = metadata.is_active
        existing.last_synced_at = metadata.last_synced_at
        db.flush()
        return existing

    def upsert_candles(self, db: Session, candles: list[NormalizedCandle]) -> int:
        inserted_or_updated = 0
        for candle in candles:
            existing = db.scalar(
                select(MarketCandle).where(
                    MarketCandle.provider == candle.provider,
                    MarketCandle.symbol == candle.symbol,
                    MarketCandle.interval == candle.interval,
                    MarketCandle.open_time == candle.open_time,
                )
            )
            if existing is None:
                existing = MarketCandle(
                    provider=candle.provider,
                    asset_class=candle.asset_class,
                    symbol=candle.symbol,
                    interval=candle.interval,
                    open_time=candle.open_time,
                )
                db.add(existing)

            existing.close_time = candle.close_time
            existing.open_price = candle.open_price
            existing.high_price = candle.high_price
            existing.low_price = candle.low_price
            existing.close_price = candle.close_price
            existing.volume = candle.volume
            existing.vwap = candle.vwap
            existing.trade_count = candle.trade_count
            existing.is_closed = candle.is_closed
            existing.source_updated_at = candle.source_updated_at
            inserted_or_updated += 1

        db.flush()
        return inserted_or_updated

    def cache_quote(self, quote: NormalizedQuote, ttl_seconds: int = 30) -> None:
        if self.redis_client is None:
            return

        payload = {
            "provider": quote.provider.value,
            "asset_class": quote.asset_class.value,
            "symbol": quote.symbol,
            "bid": str(quote.bid) if quote.bid is not None else None,
            "ask": str(quote.ask) if quote.ask is not None else None,
            "last": str(quote.last),
            "mark": str(quote.mark),
            "volume_24h": str(quote.volume_24h) if quote.volume_24h is not None else None,
            "as_of": quote.as_of.isoformat(),
        }
        self.redis_client.set(self._quote_key(quote.provider.value, quote.symbol), json.dumps(payload), ex=ttl_seconds)

    def get_cached_quote(self, provider: str, symbol: str) -> NormalizedQuote | None:
        if self.redis_client is None:
            return None

        raw_value = self.redis_client.get(self._quote_key(provider, symbol))
        if raw_value is None:
            return None

        payload = json.loads(raw_value)
        return NormalizedQuote(
            provider=payload["provider"],
            asset_class=payload["asset_class"],
            symbol=payload["symbol"],
            bid=Decimal(payload["bid"]) if payload["bid"] is not None else None,
            ask=Decimal(payload["ask"]) if payload["ask"] is not None else None,
            last=Decimal(payload["last"]),
            mark=Decimal(payload["mark"]),
            volume_24h=Decimal(payload["volume_24h"]) if payload["volume_24h"] is not None else None,
            as_of=datetime.fromisoformat(payload["as_of"]),
        )

    def _quote_key(self, provider: str, symbol: str) -> str:
        normalized_symbol = symbol.replace("/", "_")
        return f"market_quote:{provider}:{normalized_symbol}"
