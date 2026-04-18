from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal

from sqlalchemy import delete, select, tuple_
from sqlalchemy.orm import Session

from app.models.ai_research import FeatureDefinitionVersion, HistoricalFeatureRow, HistoricalUniverseSnapshot
from app.services.historical.feature_builder import FeatureBuilderService
from app.services.historical.feature_schemas import HistoricalFeatureRecord
from app.services.historical.feature_store_schemas import (
    FeatureDefinitionVersionRecord,
    HistoricalFeatureStoreBuildSummary,
    HistoricalFeatureStoreRowRecord,
)
from app.services.historical.schemas import HistoricalCandleRecord


def _normalize_values(values: dict[str, Decimal]) -> dict[str, str]:
    return {key: format(value, "f") for key, value in values.items()}


class HistoricalFeatureStoreService:
    def __init__(
        self,
        session: Session,
        *,
        builder: FeatureBuilderService | None = None,
    ) -> None:
        self._session = session
        self._builder = builder or FeatureBuilderService()

    def register_feature_definition(self) -> FeatureDefinitionVersionRecord:
        existing = self._session.get(FeatureDefinitionVersion, self._builder.FEATURE_VERSION)
        feature_keys = self._discover_feature_keys()
        if existing is None:
            existing = FeatureDefinitionVersion(
                feature_version=self._builder.FEATURE_VERSION,
                warmup_period=self._builder.warmup_period,
                feature_keys_json=feature_keys,
            )
            self._session.add(existing)
            self._session.flush()
        return FeatureDefinitionVersionRecord(
            feature_version=existing.feature_version,
            feature_keys=list(existing.feature_keys_json),
            warmup_period=existing.warmup_period,
            created_at=existing.created_at,
        )

    def build_for_decision_date(
        self,
        *,
        decision_date: date,
        asset_class: str,
        timeframe: str,
        source_label: str,
        candles_by_symbol: Mapping[str, Sequence[HistoricalCandleRecord]],
    ) -> HistoricalFeatureStoreBuildSummary:
        self.register_feature_definition()

        universe_rows = list(
            self._session.scalars(
                select(HistoricalUniverseSnapshot).where(
                    HistoricalUniverseSnapshot.decision_date == decision_date,
                    HistoricalUniverseSnapshot.asset_class == asset_class,
                ).order_by(HistoricalUniverseSnapshot.symbol.asc())
            )
        )
        records: list[HistoricalFeatureRecord] = []
        symbols_built = 0
        for row in universe_rows:
            candles = list(candles_by_symbol.get(row.symbol, ()))
            if not candles:
                continue
            built_rows = self._builder.build_feature_rows(candles)
            matched = [
                item
                for item in built_rows
                if item.candle_time.date() <= decision_date
                and item.timeframe == timeframe
                and item.source_label == source_label
            ]
            if not matched:
                continue
            symbols_built += 1
            records.extend(matched)

        replaced = self.persist_rows(decision_date=decision_date, records=records)
        return HistoricalFeatureStoreBuildSummary(
            decision_date=decision_date,
            asset_class=asset_class,
            timeframe=timeframe,
            source_label=source_label,
            symbols_requested=len(universe_rows),
            symbols_built=symbols_built,
            rows_inserted=len(records),
            rows_replaced=replaced,
            feature_version=self._builder.FEATURE_VERSION,
        )

    def persist_rows(
        self,
        *,
        decision_date: date,
        records: Sequence[HistoricalFeatureRecord],
    ) -> int:
        items = list(records)
        replaced = self._replace_existing(decision_date=decision_date, records=items)
        for item in items:
            self._session.add(
                HistoricalFeatureRow(
                    decision_date=decision_date,
                    symbol=item.symbol,
                    asset_class=item.asset_class,
                    timeframe=item.timeframe,
                    candle_time=item.candle_time,
                    source_label=item.source_label,
                    feature_version=item.feature_version,
                    values_json=_normalize_values(item.values),
                )
            )
        self._session.flush()
        return replaced

    def list_rows(
        self,
        *,
        decision_date: date,
        asset_class: str,
        timeframe: str,
    ) -> list[HistoricalFeatureStoreRowRecord]:
        rows = list(
            self._session.scalars(
                select(HistoricalFeatureRow).where(
                    HistoricalFeatureRow.decision_date == decision_date,
                    HistoricalFeatureRow.asset_class == asset_class,
                    HistoricalFeatureRow.timeframe == timeframe,
                ).order_by(HistoricalFeatureRow.symbol.asc(), HistoricalFeatureRow.candle_time.asc())
            )
        )
        return [
            HistoricalFeatureStoreRowRecord(
                decision_date=row.decision_date,
                symbol=row.symbol,
                asset_class=row.asset_class,
                timeframe=row.timeframe,
                candle_time=row.candle_time,
                source_label=row.source_label,
                feature_version=row.feature_version,
                values=dict(row.values_json),
            )
            for row in rows
        ]

    def _replace_existing(
        self,
        *,
        decision_date: date,
        records: Sequence[HistoricalFeatureRecord],
    ) -> int:
        if not records:
            return 0
        result = self._session.execute(
            delete(HistoricalFeatureRow).where(
                tuple_(
                    HistoricalFeatureRow.decision_date,
                    HistoricalFeatureRow.symbol,
                    HistoricalFeatureRow.asset_class,
                    HistoricalFeatureRow.timeframe,
                    HistoricalFeatureRow.candle_time,
                    HistoricalFeatureRow.source_label,
                    HistoricalFeatureRow.feature_version,
                ).in_(
                    [
                        (
                            decision_date,
                            item.symbol,
                            item.asset_class,
                            item.timeframe,
                            item.candle_time,
                            item.source_label,
                            item.feature_version,
                        )
                        for item in records
                    ]
                )
            )
        )
        return int(result.rowcount or 0)

    def _discover_feature_keys(self) -> list[str]:
        sample_candles = _build_feature_discovery_series(self._builder.warmup_period)
        row = self._builder.build_latest_feature_row(sample_candles)
        if row is None:
            raise ValueError("unable to discover feature keys")
        return sorted(row.values.keys())


def _build_feature_discovery_series(length: int) -> list[HistoricalCandleRecord]:
    from datetime import UTC, datetime, timedelta

    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles: list[HistoricalCandleRecord] = []
    for index in range(length):
        close = Decimal(100 + index)
        candles.append(
            HistoricalCandleRecord(
                symbol="DISCOVERY",
                asset_class="stock",
                timeframe="1h",
                candle_time=start + timedelta(hours=index),
                open=close - Decimal("1"),
                high=close + Decimal("1"),
                low=close - Decimal("2"),
                close=close,
                volume=Decimal(1000 + index),
                source_label="alpaca",
                fetched_at=start + timedelta(days=1),
                retention_bucket="intraday_medium",
            )
        )
    return candles