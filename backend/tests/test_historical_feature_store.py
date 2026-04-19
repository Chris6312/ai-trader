from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import AssetClass
from app.services.historical.historical_feature_store import HistoricalFeatureStoreService
from app.services.historical.historical_universe_snapshot import HistoricalUniverseSnapshotService
from app.services.historical.schemas import HistoricalCandleRecord
from app.services.symbol_registry import SymbolRegistrySeed, SymbolRegistryService


def _build_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed_universe(session: Session, *, seen_at: datetime) -> None:
    registry_service = SymbolRegistryService()
    snapshot_service = HistoricalUniverseSnapshotService(session)
    registry_service.seed(
        session,
        [
            SymbolRegistrySeed(
                symbol="AAPL",
                asset_class=AssetClass.STOCK,
                source="sp500",
                history_status="ready",
                first_seen_at=seen_at,
                last_seen_at=seen_at,
            ),
            SymbolRegistrySeed(
                symbol="MSFT",
                asset_class=AssetClass.STOCK,
                source="sp500",
                history_status="ready",
                first_seen_at=seen_at,
                last_seen_at=seen_at,
            ),
        ],
        seen_at=seen_at,
    )
    snapshot_service.freeze_from_symbol_registry(
        decision_date=seen_at.date(),
        asset_class=AssetClass.STOCK,
        source_label="phase12b_test",
    )
    session.commit()


def _build_candles(symbol: str, *, start: datetime) -> list[HistoricalCandleRecord]:
    candles: list[HistoricalCandleRecord] = []
    for index in range(26):
        close = Decimal(100 + index)
        candles.append(
            HistoricalCandleRecord(
                symbol=symbol,
                asset_class="stock",
                timeframe="1h",
                candle_time=start + timedelta(hours=index),
                open=close - Decimal("1"),
                high=close + Decimal("1"),
                low=close - Decimal("2"),
                close=close,
                volume=Decimal(1000 + index * 10),
                source_label="alpaca",
                fetched_at=start + timedelta(days=1),
                retention_bucket="intraday_medium",
            )
        )
    return candles


def test_historical_feature_store_builds_only_for_frozen_universe_symbols() -> None:
    session = _build_session()
    seen_at = datetime(2026, 4, 18, 12, 0, tzinfo=UTC)
    _seed_universe(session, seen_at=seen_at)
    service = HistoricalFeatureStoreService(session)

    summary = service.build_for_decision_date(
        decision_date=seen_at.date(),
        asset_class="stock",
        timeframe="1h",
        source_label="alpaca",
        candles_by_symbol={
            "AAPL": _build_candles("AAPL", start=datetime(2026, 4, 17, 0, 0, tzinfo=UTC)),
            "MSFT": _build_candles("MSFT", start=datetime(2026, 4, 17, 0, 0, tzinfo=UTC)),
            "NVDA": _build_candles("NVDA", start=datetime(2026, 4, 17, 0, 0, tzinfo=UTC)),
        },
    )
    session.commit()

    rows = service.list_rows(decision_date=seen_at.date(), asset_class="stock", timeframe="1h")

    assert summary.symbols_requested == 2
    assert summary.symbols_built == 2
    assert summary.rows_inserted == 14
    assert sorted({row.symbol for row in rows}) == ["AAPL", "MSFT"]
    assert all(row.decision_date == seen_at.date() for row in rows)
    assert all(row.feature_version == "11c_v1" for row in rows)


def test_historical_feature_store_rows_remain_point_in_time_safe() -> None:
    session = _build_session()
    seen_at = datetime(2026, 4, 18, 12, 0, tzinfo=UTC)
    _seed_universe(session, seen_at=seen_at)
    service = HistoricalFeatureStoreService(session)
    candles = _build_candles("AAPL", start=datetime(2026, 4, 17, 0, 0, tzinfo=UTC))
    first_summary = service.build_for_decision_date(
        decision_date=seen_at.date(),
        asset_class="stock",
        timeframe="1h",
        source_label="alpaca",
        candles_by_symbol={"AAPL": candles, "MSFT": _build_candles("MSFT", start=datetime(2026, 4, 17, 0, 0, tzinfo=UTC))},
    )
    session.commit()

    original_rows = service.list_rows(decision_date=seen_at.date(), asset_class="stock", timeframe="1h")
    original_aapl = [row for row in original_rows if row.symbol == "AAPL"]
    assert original_aapl
    last_original = original_aapl[-1]
    assert last_original.candle_time.date() == seen_at.date()

    future_candles = list(candles)
    future_candles.append(
        HistoricalCandleRecord(
            symbol="AAPL",
            asset_class="stock",
            timeframe="1h",
            candle_time=datetime(2026, 4, 19, 2, 0, tzinfo=UTC),
            open=Decimal("999"),
            high=Decimal("1000"),
            low=Decimal("998"),
            close=Decimal("999"),
            volume=Decimal("9999"),
            source_label="alpaca",
            fetched_at=datetime(2026, 4, 19, 3, 0, tzinfo=UTC),
            retention_bucket="intraday_medium",
        )
    )
    second_summary = service.build_for_decision_date(
        decision_date=seen_at.date(),
        asset_class="stock",
        timeframe="1h",
        source_label="alpaca",
        candles_by_symbol={"AAPL": future_candles, "MSFT": _build_candles("MSFT", start=datetime(2026, 4, 17, 0, 0, tzinfo=UTC))},
    )
    session.commit()

    rebuilt_rows = service.list_rows(decision_date=seen_at.date(), asset_class="stock", timeframe="1h")
    rebuilt_aapl = [row for row in rebuilt_rows if row.symbol == "AAPL"]

    assert first_summary.rows_inserted == second_summary.rows_inserted
    assert second_summary.rows_replaced == second_summary.rows_inserted
    assert [row.candle_time for row in rebuilt_aapl] == [row.candle_time for row in original_aapl]
    assert rebuilt_aapl[-1].values == original_aapl[-1].values


def test_historical_feature_store_registers_feature_definition_version() -> None:
    session = _build_session()
    service = HistoricalFeatureStoreService(session)

    definition = service.register_feature_definition()
    duplicate = service.register_feature_definition()

    assert definition.feature_version == "11c_v1"
    assert definition.warmup_period == 20
    assert definition.feature_keys == sorted(definition.feature_keys)
    assert duplicate.feature_version == definition.feature_version
    assert duplicate.feature_keys == definition.feature_keys
