from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.market_data.schemas import NormalizedCandle
from app.models import AssetClass, CandleInterval, MarketDataProvider
from app.services.market_data import MarketDataService


class FakeRedis:
    def __init__(self) -> None:
        self.storage: dict[str, str] = {}

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.storage[key] = value

    def get(self, key: str) -> str | None:
        return self.storage.get(key)


def _build_session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def test_market_data_service_reads_cached_quote_and_recent_candles() -> None:
    redis_client = FakeRedis()
    service = MarketDataService(redis_client=redis_client)
    redis_client.set(
        "market-data:quote:BTC/USD",
        json.dumps(
            {
                "provider": "kraken",
                "asset_class": "crypto",
                "symbol": "BTC/USD",
                "bid": "64000",
                "ask": "64010",
                "last": "64005",
                "mark": "64005",
                "volume_24h": "100",
                "as_of": "2026-04-17T21:05:00+00:00",
            }
        ),
    )

    maker = _build_session_factory()
    with maker() as db:
        service.upsert_candles(
            db,
            [
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
                ),
                NormalizedCandle(
                    provider=MarketDataProvider.KRAKEN,
                    asset_class=AssetClass.CRYPTO,
                    symbol="BTC/USD",
                    interval=CandleInterval.MINUTE_5,
                    open_time=datetime(2026, 4, 17, 21, 5, tzinfo=UTC),
                    close_time=datetime(2026, 4, 17, 21, 10, tzinfo=UTC),
                    open_price=Decimal("64005"),
                    high_price=Decimal("64050"),
                    low_price=Decimal("63980"),
                    close_price=Decimal("64025"),
                    volume=Decimal("11"),
                    vwap=Decimal("64010"),
                    trade_count=45,
                    is_closed=True,
                    source_updated_at=datetime(2026, 4, 17, 21, 10, tzinfo=UTC),
                ),
            ],
        )
        db.commit()

        candles = service.list_recent_candles(
            db,
            symbol="BTC/USD",
            interval=CandleInterval.MINUTE_5,
            limit=2,
        )

    quote = service.get_cached_quote("BTC/USD")
    audit = service.get_fetch_audit(worker_enabled=True)

    assert quote is not None
    assert quote["symbol"] == "BTC/USD"
    assert quote["last"] == Decimal("64005")
    assert len(candles) == 2
    assert candles[0].open_time > candles[1].open_time
    assert audit["closed_candle_owner"] == "candle_worker"
    assert audit["duplicate_fetch_paths_detected"] is False
