from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.models import CandleInterval
from app.services.candle_scheduler import eligible_close_time, next_fetch_time


class CandleWorker:
    def __init__(
        self,
        *,
        sync_service,
        crypto_symbols: tuple[str, ...] = (),
        stock_symbols: tuple[str, ...] = (),
        intervals: tuple[str, ...] = ("5m", "15m", "1h"),
        fetch_delay_seconds: int = 20,
    ) -> None:
        self.sync_service = sync_service
        self.crypto_symbols = crypto_symbols
        self.stock_symbols = stock_symbols
        self.intervals = intervals
        self.fetch_delay_seconds = fetch_delay_seconds
        self._stop_event = asyncio.Event()
        self._last_processed_close_by_interval: dict[str, datetime] = {}

    async def run_once(self, now: datetime | None = None) -> dict[str, object]:
        now = now or datetime.now(timezone.utc)
        due_intervals: list[str] = []

        for interval in self.intervals:
            close_time = eligible_close_time(
                now,
                interval,
                delay_seconds=self.fetch_delay_seconds,
            )
            if self._last_processed_close_by_interval.get(interval) == close_time:
                continue
            due_intervals.append(interval)

        if not due_intervals:
            return {"quotes_cached": 0, "intervals_processed": [], "stored": 0, "skipped": 0}

        quotes_cached = await self.sync_service.sync_quotes(
            crypto_symbols=self.crypto_symbols,
            stock_symbols=self.stock_symbols,
        )

        stored = 0
        skipped = 0
        processed: list[str] = []

        for interval in due_intervals:
            close_time = eligible_close_time(
                now,
                interval,
                delay_seconds=self.fetch_delay_seconds,
            )
            result = await self.sync_service.sync_closed_candles(
                crypto_symbols=self.crypto_symbols,
                stock_symbols=self.stock_symbols,
                interval=CandleInterval(interval),
                as_of=now,
            )
            self._last_processed_close_by_interval[interval] = close_time
            stored += result.stored
            skipped += result.skipped
            processed.append(interval)

        return {
            "quotes_cached": quotes_cached,
            "intervals_processed": processed,
            "stored": stored,
            "skipped": skipped,
        }

    async def run(self) -> None:
        while not self._stop_event.is_set():
            now = datetime.now(timezone.utc)
            next_runs = [
                next_fetch_time(
                    now,
                    interval,
                    delay_seconds=self.fetch_delay_seconds,
                )
                for interval in self.intervals
            ]
            sleep_seconds = min((scheduled_at - now).total_seconds() for scheduled_at in next_runs)
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=max(1.0, sleep_seconds))
                break
            except asyncio.TimeoutError:
                await self.run_once()

    def stop(self) -> None:
        self._stop_event.set()
