from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models import AssetClass
from app.services.symbol_registry import SymbolRegistrySeed, SymbolRegistryService


def _build_session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def test_symbol_registry_service_seeds_and_updates_symbols_without_duplicates() -> None:
    maker = _build_session_factory()
    service = SymbolRegistryService()
    seen_at = datetime(2026, 4, 18, 12, 40, tzinfo=UTC)

    with maker() as db:
        first_pass = service.seed(
            db,
            [
                SymbolRegistrySeed(
                    symbol="aapl",
                    asset_class=AssetClass.STOCK,
                    source="sp500",
                    sector_or_category="Technology",
                    avg_dollar_volume=Decimal("125000000.50"),
                    first_seen_at=seen_at,
                    last_seen_at=seen_at,
                ),
                SymbolRegistrySeed(
                    symbol="AAPL",
                    asset_class=AssetClass.STOCK,
                    source="nasdaq100",
                    sector_or_category="Technology",
                    avg_dollar_volume=Decimal("126000000.00"),
                    first_seen_at=seen_at,
                    last_seen_at=seen_at,
                    metadata_json={"index_memberships": ["nasdaq100"]},
                ),
            ],
            seen_at=seen_at,
        )
        db.commit()

        second_seen_at = datetime(2026, 4, 19, 12, 40, tzinfo=UTC)
        second_pass = service.seed(
            db,
            [
                SymbolRegistrySeed(
                    symbol="AAPL",
                    asset_class=AssetClass.STOCK,
                    source="sp500",
                    sector_or_category="Tech",
                    avg_dollar_volume=Decimal("130000000.00"),
                    history_status="ready",
                    first_seen_at=seen_at,
                    last_seen_at=second_seen_at,
                    metadata_json={"index_memberships": ["sp500"]},
                )
            ],
            seen_at=second_seen_at,
        )
        db.commit()

        rows = service.list_symbols(db, asset_class=AssetClass.STOCK)

    assert len(first_pass) == 1
    assert len(second_pass) == 1
    assert len(rows) == 1
    assert rows[0].symbol == "AAPL"
    assert rows[0].source == "sp500"
    assert rows[0].sector_or_category == "Tech"
    assert rows[0].avg_dollar_volume == Decimal("130000000.00")
    assert rows[0].history_status == "ready"
    assert _as_utc(rows[0].first_seen_at) == seen_at
    assert _as_utc(rows[0].last_seen_at) == second_seen_at
    assert rows[0].metadata_json == {"index_memberships": ["sp500"]}


def test_symbol_registry_service_builds_kraken_registry_seeds_with_display_aliases() -> None:
    service = SymbolRegistryService()
    seen_at = datetime(2026, 4, 18, 12, 40, tzinfo=UTC)

    seeds = service.build_kraken_seeds(
        [
            {
                "symbol": "XXBTZUSD",
                "altname": "XBTUSD",
                "wsname": "XBT/USD",
                "base": "XXBT",
                "quote": "ZUSD",
            },
            {
                "symbol": "XETHZUSD",
                "altname": "ETHUSD",
                "wsname": "ETH/USD",
                "base": "XETH",
                "quote": "ZUSD",
            },
        ],
        seen_at=seen_at,
    )

    assert [seed.symbol for seed in seeds] == ["BTC/USD", "ETH/USD"]
    assert all(seed.asset_class == AssetClass.CRYPTO for seed in seeds)
    assert all(seed.source == "kraken_csv" for seed in seeds)
    assert seeds[0].metadata_json["provider_symbol"] == "XXBTZUSD"
    assert seeds[0].first_seen_at == seen_at