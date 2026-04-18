from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from app.services.historical.historical_backfill_service import HistoricalBackfillService
from app.services.historical.schemas import HistoricalCandleRecord


class FakeRepo:
    def __init__(self) -> None:
        self.latest = {}
        self.saved: list[HistoricalCandleRecord] = []

    def get_latest_candle_ts(self, db, *, symbol: str, asset_class: str, timeframe: str):
        return self.latest.get((symbol, asset_class, timeframe))

    def insert_many_ignore_duplicates(self, db, *, candles: list[HistoricalCandleRecord]) -> int:
        self.saved.extend(candles)
        return len(candles)


class FakeAlpaca:
    def fetch_batch(self, *, symbols, timeframe, start_at, end_at):
        return [
            HistoricalCandleRecord(
                symbol=symbols[0],
                asset_class="stock",
                timeframe=timeframe,
                candle_time=start_at,
                open=Decimal("1"),
                high=Decimal("2"),
                low=Decimal("0.5"),
                close=Decimal("1.5"),
                volume=Decimal("10"),
                source_label="alpaca",
                fetched_at=end_at,
                retention_bucket="intraday_medium",
            )
        ]


class FakeKraken:
    def load_directory(self, *, directory: Path, timeframe: str):
        return [
            HistoricalCandleRecord(
                symbol="BTC/USD",
                asset_class="crypto",
                timeframe=timeframe,
                candle_time=datetime(2026, 1, 1, tzinfo=UTC),
                open=Decimal("42000"),
                high=Decimal("42500"),
                low=Decimal("41800"),
                close=Decimal("42300"),
                volume=Decimal("12"),
                source_label="kraken_csv",
                fetched_at=datetime(2026, 4, 18, tzinfo=UTC),
                retention_bucket="intraday_medium",
            )
        ]


def test_backfill_stock_symbols_returns_summary() -> None:
    service = HistoricalBackfillService(
        candle_repository=FakeRepo(),
        alpaca_fetcher=FakeAlpaca(),
    )

    summaries = service.backfill_stock_symbols(
        None,
        symbols=["AAPL"],
        timeframe="1h",
        start_at=datetime(2026, 1, 1, tzinfo=UTC),
        end_at=datetime(2026, 1, 2, tzinfo=UTC),
    )

    assert len(summaries) == 1
    assert summaries[0].symbol == "AAPL"
    assert summaries[0].source_label == "alpaca"
    assert summaries[0].rows_read == 1
    assert summaries[0].rows_inserted == 1


def test_backfill_crypto_from_csv_returns_summary(tmp_path: Path) -> None:
    service = HistoricalBackfillService(
        candle_repository=FakeRepo(),
        kraken_csv_loader=FakeKraken(),
    )

    summaries = service.backfill_crypto_from_csv(
        None,
        directory=tmp_path,
        timeframe="1h",
    )

    assert len(summaries) == 1
    assert summaries[0].symbol == "BTC/USD"
    assert summaries[0].source_label == "kraken_csv"
    assert summaries[0].rows_read == 1
