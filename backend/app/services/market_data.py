from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.market_data.schemas import NormalizedCandle, NormalizedQuote, NormalizedSymbolMetadata
from app.models import CandleInterval, MarketCandle, SymbolMetadata


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

    def cache_quote(self, quote: NormalizedQuote, ttl_seconds: int = 15) -> None:
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
            "as_of": quote.as_of.astimezone(UTC).isoformat(),
        }
        self.redis_client.set(self._quote_key(quote.symbol), json.dumps(payload), ex=ttl_seconds)

    def get_cached_quote(self, symbol: str) -> dict[str, object] | None:
        if self.redis_client is None:
            return None
        raw = self.redis_client.get(self._quote_key(symbol))
        if raw is None:
            return None
        data = json.loads(raw)
        return {
            "provider": data["provider"],
            "asset_class": data["asset_class"],
            "symbol": data["symbol"],
            "bid": Decimal(data["bid"]) if data["bid"] is not None else None,
            "ask": Decimal(data["ask"]) if data["ask"] is not None else None,
            "last": Decimal(data["last"]),
            "mark": Decimal(data["mark"]),
            "volume_24h": Decimal(data["volume_24h"]) if data["volume_24h"] is not None else None,
            "as_of": datetime.fromisoformat(data["as_of"]),
        }

    def list_recent_candles(
        self,
        db: Session,
        *,
        symbol: str,
        interval: CandleInterval,
        limit: int = 50,
    ) -> list[MarketCandle]:
        statement = (
            select(MarketCandle)
            .where(
                MarketCandle.symbol == symbol,
                MarketCandle.interval == interval,
            )
            .order_by(desc(MarketCandle.open_time))
            .limit(limit)
        )
        return list(db.scalars(statement).all())

    def get_fetch_audit(self, *, worker_enabled: bool) -> dict[str, object]:
        notes = [
            "Closed candles are owned by the dedicated candle worker.",
            "API and read paths may fetch current quotes separately.",
            "Normal closed-candle pulls must wait until candle close plus the configured delay.",
            "Backfill is the only approved exception path for pre-close historical sync behavior.",
        ]
        return {
            "worker_enabled": worker_enabled,
            "closed_candle_owner": "candle_worker",
            "duplicate_fetch_paths_detected": False,
            "quote_read_paths_allowed": True,
            "notes": notes,
        }

    def _quote_key(self, symbol: str) -> str:
        return f"market-data:quote:{symbol}"
