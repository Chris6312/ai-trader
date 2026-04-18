from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.services.historical.alpaca_fetcher import AlpacaHistoricalFetcher
from app.services.historical.backfill_planner import BackfillPlanner
from app.services.historical.candle_repository import CandleRepository
from app.services.historical.kraken_csv_loader import KrakenCsvLoader
from app.services.historical.schemas import IngestionSummary


class HistoricalBackfillService:
    def __init__(
        self,
        *,
        candle_repository: CandleRepository | None = None,
        backfill_planner: BackfillPlanner | None = None,
        alpaca_fetcher: AlpacaHistoricalFetcher | None = None,
        kraken_csv_loader: KrakenCsvLoader | None = None,
    ) -> None:
        self.candle_repository = candle_repository or CandleRepository()
        self.backfill_planner = backfill_planner or BackfillPlanner()
        self.alpaca_fetcher = alpaca_fetcher or AlpacaHistoricalFetcher()
        self.kraken_csv_loader = kraken_csv_loader or KrakenCsvLoader()

    def backfill_stock_symbols(
        self,
        db,
        *,
        symbols: list[str],
        timeframe: str,
        start_at: datetime,
        end_at: datetime,
    ) -> list[IngestionSummary]:
        summaries: list[IngestionSummary] = []
        for symbol in symbols:
            latest = self.candle_repository.get_latest_candle_ts(
                db,
                symbol=symbol,
                asset_class="stock",
                timeframe=timeframe,
            )
            plan = self.backfill_planner.plan_incremental(
                symbol=symbol,
                asset_class="stock",
                timeframe=timeframe,
                latest_candle_ts=latest,
                requested_end_at=end_at,
                bootstrap_start_at=start_at,
            )
            if not plan.should_fetch or plan.fetch_start_at is None:
                summaries.append(
                    IngestionSummary(
                        symbol=symbol,
                        asset_class="stock",
                        timeframe=timeframe,
                        source_label="alpaca",
                        rows_read=0,
                        rows_inserted=0,
                        rows_skipped_duplicate=0,
                        rows_skipped_out_of_range=0,
                    )
                )
                continue

            rows = self.alpaca_fetcher.fetch_batch(
                symbols=[symbol],
                timeframe=timeframe,
                start_at=plan.fetch_start_at,
                end_at=plan.fetch_end_at,
            )
            inserted = self.candle_repository.insert_many_ignore_duplicates(db, candles=rows)
            summaries.append(
                IngestionSummary(
                    symbol=symbol,
                    asset_class="stock",
                    timeframe=timeframe,
                    source_label="alpaca",
                    rows_read=len(rows),
                    rows_inserted=inserted,
                    rows_skipped_duplicate=max(0, len(rows) - inserted),
                    rows_skipped_out_of_range=0,
                )
            )
        return summaries

    def backfill_crypto_from_csv(
        self,
        db,
        *,
        directory: Path,
        timeframe: str,
    ) -> list[IngestionSummary]:
        rows = self.kraken_csv_loader.load_directory(
            directory=directory,
            timeframe=timeframe,
        )
        inserted = self.candle_repository.insert_many_ignore_duplicates(db, candles=rows)

        grouped: dict[str, int] = {}
        for row in rows:
            grouped[row.symbol] = grouped.get(row.symbol, 0) + 1

        summaries: list[IngestionSummary] = []
        for symbol, count in sorted(grouped.items()):
            # approximate duplicate count by symbol distribution
            summaries.append(
                IngestionSummary(
                    symbol=symbol,
                    asset_class="crypto",
                    timeframe=timeframe,
                    source_label="kraken_csv",
                    rows_read=count,
                    rows_inserted=count,
                    rows_skipped_duplicate=0,
                    rows_skipped_out_of_range=0,
                )
            )
        if rows and inserted < len(rows):
            # keep summary conservative if duplicates were skipped in aggregate
            skipped = len(rows) - inserted
            if summaries:
                first = summaries[0]
                summaries[0] = IngestionSummary(
                    symbol=first.symbol,
                    asset_class=first.asset_class,
                    timeframe=first.timeframe,
                    source_label=first.source_label,
                    rows_read=first.rows_read,
                    rows_inserted=max(0, first.rows_inserted - skipped),
                    rows_skipped_duplicate=skipped,
                    rows_skipped_out_of_range=0,
                )
        return summaries
