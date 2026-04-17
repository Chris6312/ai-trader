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
        self.candle_calls: list[tuple[CandleInterval, bool]] = []

    async def sync_quotes(self, *, crypto_symbols, stock_symbols) -> int:
        self.quote_calls += 1
        return len(crypto_symbols) + len(stock_symbols)

    async def sync_closed_candles(self, *, crypto_symbols, stock_symbols, interval, as_of, backfill=False):
        self.candle_calls.append((interval, backfill))
        return FakeResult(stored=1, skipped=0)

    def get_provider_readiness(self) -> dict[str, dict[str, object]]:
        return {
            "kraken": {"provider": "kraken", "configured": True, "details": None},
            "tradier": {"provider": "tradier", "configured": False, "details": "Missing Tradier API token."},
        }


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
    assert sync_service.candle_calls == [
        (CandleInterval.MINUTE_5, False),
        (CandleInterval.DAY_1, False),
    ]
    assert second["intervals_processed"] == []


@pytest.mark.asyncio
async def test_worker_backfill_mode_reprocesses_current_slot() -> None:
    sync_service = FakeSyncService()
    worker = CandleWorker(
        sync_service=sync_service,
        crypto_symbols=("BTC/USD",),
        stock_symbols=("AAPL",),
        intervals=("5m",),
        fetch_delay_seconds=20,
    )

    now = datetime(2026, 1, 1, 10, 5, 21, tzinfo=timezone.utc)
    await worker.run_once(now=now)
    result = await worker.run_once(now=now, backfill=True)

    assert result["backfill"] is True
    assert result["intervals_processed"] == ["5m"]
    assert sync_service.candle_calls == [
        (CandleInterval.MINUTE_5, False),
        (CandleInterval.MINUTE_5, True),
    ]


@pytest.mark.asyncio
async def test_worker_status_surfaces_provider_readiness() -> None:
    worker = CandleWorker(
        sync_service=FakeSyncService(),
        crypto_symbols=("BTC/USD",),
        stock_symbols=("AAPL",),
        intervals=("5m",),
        fetch_delay_seconds=20,
    )

    await worker.run_once(now=datetime(2026, 1, 1, 10, 5, 21, tzinfo=timezone.utc))
    status = worker.get_status()

    assert status["last_result"] is not None
    assert status["provider_readiness"]["kraken"]["configured"] is True
    assert status["provider_readiness"]["tradier"]["configured"] is False
