from __future__ import annotations

import asyncio
from datetime import UTC, datetime

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
        self._last_run_started_at: datetime | None = None
        self._last_run_finished_at: datetime | None = None
        self._last_error: str | None = None
        self._last_result: dict[str, object] | None = None
        self._next_scheduled_run_at: datetime | None = None
        self._is_running = False

    async def run_once(self, now: datetime | None = None) -> dict[str, object]:
        now = now or datetime.now(UTC)
        self._last_run_started_at = now
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
            result = {"quotes_cached": 0, "intervals_processed": [], "stored": 0, "skipped": 0}
            self._last_result = result
            self._last_run_finished_at = now
            self._last_error = None
            return result

        try:
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

            final_result = {
                "quotes_cached": quotes_cached,
                "intervals_processed": processed,
                "stored": stored,
                "skipped": skipped,
            }
            self._last_result = final_result
            self._last_error = None
            return final_result
        except Exception as exc:
            self._last_error = str(exc)
            raise
        finally:
            self._last_run_finished_at = datetime.now(UTC)

    async def run(self) -> None:
        self._is_running = True
        try:
            while not self._stop_event.is_set():
                now = datetime.now(UTC)
                next_runs = [
                    next_fetch_time(
                        now,
                        interval,
                        delay_seconds=self.fetch_delay_seconds,
                    )
                    for interval in self.intervals
                ]
                self._next_scheduled_run_at = min(next_runs)
                sleep_seconds = min((scheduled_at - now).total_seconds() for scheduled_at in next_runs)
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=max(1.0, sleep_seconds))
                    break
                except asyncio.TimeoutError:
                    await self.run_once()
        finally:
            self._is_running = False
            self._next_scheduled_run_at = None

    def stop(self) -> None:
        self._stop_event.set()

    def get_status(self) -> dict[str, object]:
        provider_readiness_getter = getattr(self.sync_service, "get_provider_readiness", None)
        provider_readiness = provider_readiness_getter() if callable(provider_readiness_getter) else {}

        return {
            "running": self._is_running,
            "fetch_delay_seconds": self.fetch_delay_seconds,
            "crypto_symbols": list(self.crypto_symbols),
            "stock_symbols": list(self.stock_symbols),
            "intervals": list(self.intervals),
            "next_scheduled_run_at": self._iso(self._next_scheduled_run_at),
            "last_run_started_at": self._iso(self._last_run_started_at),
            "last_run_finished_at": self._iso(self._last_run_finished_at),
            "last_error": self._last_error,
            "last_result": self._last_result,
            "last_processed_close_by_interval": {
                key: self._iso(value) for key, value in self._last_processed_close_by_interval.items()
            },
            "provider_readiness": provider_readiness,
        }

    def _iso(self, value: datetime | None) -> str | None:
        return value.isoformat() if value is not None else None
