from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import AssetClass
from app.services.historical.historical_universe_snapshot import HistoricalUniverseSnapshotService
from app.services.symbol_registry import SymbolRegistrySeed, SymbolRegistryService


def _build_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def test_historical_universe_snapshot_freezes_membership_by_decision_date() -> None:
    session = _build_session()
    registry_service = SymbolRegistryService()
    snapshot_service = HistoricalUniverseSnapshotService(session)

    day_one = datetime(2026, 4, 18, 12, 0, tzinfo=UTC)
    day_two = datetime(2026, 4, 19, 12, 0, tzinfo=UTC)

    registry_service.seed(
        session,
        [
            SymbolRegistrySeed(
                symbol="AAPL",
                asset_class=AssetClass.STOCK,
                source="sp500",
                history_status="ready",
                avg_dollar_volume=Decimal("1000000.00"),
                first_seen_at=day_one,
                last_seen_at=day_one,
            ),
            SymbolRegistrySeed(
                symbol="NVDA",
                asset_class=AssetClass.STOCK,
                source="sp500",
                history_status="ready",
                avg_dollar_volume=Decimal("2000000.00"),
                first_seen_at=day_one,
                last_seen_at=day_one,
            ),
        ],
        seen_at=day_one,
    )
    snapshot_service.freeze_from_symbol_registry(
        decision_date=day_one.date(),
        asset_class=AssetClass.STOCK,
        source_label="phase12a_test",
    )
    session.commit()

    registry_service.seed(
        session,
        [
            SymbolRegistrySeed(
                symbol="AAPL",
                asset_class=AssetClass.STOCK,
                source="sp500",
                is_active=False,
                history_status="stale",
                avg_dollar_volume=Decimal("900000.00"),
                first_seen_at=day_one,
                last_seen_at=day_two,
            ),
            SymbolRegistrySeed(
                symbol="MSFT",
                asset_class=AssetClass.STOCK,
                source="sp500",
                history_status="ready",
                avg_dollar_volume=Decimal("3000000.00"),
                first_seen_at=day_two,
                last_seen_at=day_two,
            ),
            SymbolRegistrySeed(
                symbol="NVDA",
                asset_class=AssetClass.STOCK,
                source="sp500",
                history_status="ready",
                avg_dollar_volume=Decimal("2500000.00"),
                first_seen_at=day_one,
                last_seen_at=day_two,
            ),
        ],
        seen_at=day_two,
    )
    snapshot_service.freeze_from_symbol_registry(
        decision_date=day_two.date(),
        asset_class=AssetClass.STOCK,
        source_label="phase12a_test",
    )
    session.commit()

    day_one_symbols = snapshot_service.list_symbols(
        decision_date=day_one.date(),
        asset_class=AssetClass.STOCK,
    )
    day_two_symbols = snapshot_service.list_symbols(
        decision_date=day_two.date(),
        asset_class=AssetClass.STOCK,
    )

    assert [row.symbol for row in day_one_symbols] == ["AAPL", "NVDA"]
    assert [row.symbol for row in day_two_symbols] == ["MSFT", "NVDA"]
    assert day_one_symbols[0].history_status == "ready"
    assert day_two_symbols[0].decision_date == day_two.date()


def test_historical_universe_snapshot_keeps_stock_and_crypto_universes_separate() -> None:
    session = _build_session()
    registry_service = SymbolRegistryService()
    snapshot_service = HistoricalUniverseSnapshotService(session)
    seen_at = datetime(2026, 4, 18, 12, 0, tzinfo=UTC)

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
                symbol="BTC/USD",
                asset_class=AssetClass.CRYPTO,
                source="kraken_csv",
                history_status="ready",
                first_seen_at=seen_at,
                last_seen_at=seen_at,
                metadata_json={"provider_symbol": "XXBTZUSD"},
            ),
        ],
        seen_at=seen_at,
    )

    snapshot_service.freeze_from_symbol_registry(
        decision_date=seen_at.date(),
        asset_class=AssetClass.STOCK,
        source_label="phase12a_test",
    )
    snapshot_service.freeze_from_symbol_registry(
        decision_date=seen_at.date(),
        asset_class=AssetClass.CRYPTO,
        source_label="phase12a_test",
    )
    session.commit()

    stock_rows = snapshot_service.list_symbols(
        decision_date=seen_at.date(),
        asset_class=AssetClass.STOCK,
    )
    crypto_rows = snapshot_service.list_symbols(
        decision_date=seen_at.date(),
        asset_class=AssetClass.CRYPTO,
    )

    assert [row.symbol for row in stock_rows] == ["AAPL"]
    assert [row.symbol for row in crypto_rows] == ["BTC/USD"]
    assert crypto_rows[0].registry_source == "kraken_csv"
    assert crypto_rows[0].metadata_json == {"provider_symbol": "XXBTZUSD"}
