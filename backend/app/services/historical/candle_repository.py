from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlalchemy import select

from app.models.market_data import MarketCandle
from app.services.historical.schemas import HistoricalCandleRecord


class CandleRepository:
    def get_latest_candle_ts(
        self,
        db,
        *,
        symbol: str,
        asset_class: str,
        timeframe: str,
    ) -> datetime | None:
        stmt = (
            select(MarketCandle.candle_time)
            .where(MarketCandle.symbol == symbol)
            .where(MarketCandle.asset_class == asset_class)
            .where(MarketCandle.timeframe == timeframe)
            .order_by(MarketCandle.candle_time.desc())
            .limit(1)
        )
        return db.execute(stmt).scalar_one_or_none()

    def list_existing_timestamps(
        self,
        db,
        *,
        symbol: str,
        asset_class: str,
        timeframe: str,
        start_at: datetime,
        end_at: datetime,
    ) -> set[datetime]:
        stmt = (
            select(MarketCandle.candle_time)
            .where(MarketCandle.symbol == symbol)
            .where(MarketCandle.asset_class == asset_class)
            .where(MarketCandle.timeframe == timeframe)
            .where(MarketCandle.candle_time >= start_at)
            .where(MarketCandle.candle_time <= end_at)
        )
        return set(db.execute(stmt).scalars().all())

    def insert_many_ignore_duplicates(
        self,
        db,
        *,
        candles: list[HistoricalCandleRecord],
    ) -> int:
        inserted = 0
        for candle in candles:
            if self._exists(
                db,
                symbol=candle.symbol,
                asset_class=candle.asset_class,
                timeframe=candle.timeframe,
                candle_time=candle.candle_time,
            ):
                continue

            db.add(
                MarketCandle(
                    symbol=candle.symbol,
                    asset_class=candle.asset_class,
                    timeframe=candle.timeframe,
                    candle_time=candle.candle_time,
                    open=candle.open,
                    high=candle.high,
                    low=candle.low,
                    close=candle.close,
                    volume=candle.volume,
                    source_label=candle.source_label,
                    retention_bucket=candle.retention_bucket,
                )
            )
            inserted += 1
        return inserted

    def _exists(
        self,
        db,
        *,
        symbol: str,
        asset_class: str,
        timeframe: str,
        candle_time: datetime,
    ) -> bool:
        stmt = (
            select(MarketCandle.id)
            .where(MarketCandle.symbol == symbol)
            .where(MarketCandle.asset_class == asset_class)
            .where(MarketCandle.timeframe == timeframe)
            .where(MarketCandle.candle_time == candle_time)
            .limit(1)
        )
        return db.execute(stmt).scalar_one_or_none() is not None
