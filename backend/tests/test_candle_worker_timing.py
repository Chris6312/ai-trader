from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from app.models import CandleInterval
from app.workers.candle_worker import CandleWorker


@dataclass
class FakeResult:
    stored: int
    skipped: int


class FakeSyncService:
    def __init__(self) -> None:
        self.quote_calls = 0
        self.candle_calls: list[CandleInterval] = []

    async def sync_quotes(self, *, crypto_symbols, stock_symbols) -> int:
        self.quote_calls += 1
        return len(crypto_symbols) + len(stock_symbols)

    async def sync_closed_candles(self, *, crypto_symbols, stock_symbols, interval, as_of):
        self.candle_calls.append(interval)
        return FakeResult(stored=1, skipped=0)


@pytest.mark.asyncio
async def test_worker_processes_due_intervals_only_once_per_slot() -> None:
    sync_service = FakeSyncService()
    worker = CandleWorker(
        sync_service=sync_service,
        crypto_symbols=("BTC/USD",),
        stock_symbols=("AAPL",),
        intervals=("5m", "1d"),
        fetch_delay_seconds=20,
    )

    now = datetime(2026, 1, 1, 10, 5, 21, tzinfo=timezone.utc)
    first = await worker.run_once(now=now)
    second = await worker.run_once(now=now)

    assert first["quotes_cached"] == 2
    assert first["intervals_processed"] == ["5m", "1d"]
    assert sync_service.candle_calls == [CandleInterval.MINUTE_5, CandleInterval.DAY_1]
    assert second["intervals_processed"] == []
