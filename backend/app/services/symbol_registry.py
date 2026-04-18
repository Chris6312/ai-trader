from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models.ai_research import SymbolRegistry
from app.models.trading import AssetClass


@dataclass(slots=True)
class SymbolRegistrySeed:
    symbol: str
    asset_class: AssetClass
    source: str
    is_active: bool = True
    is_tradable: bool = True
    sector_or_category: str | None = None
    avg_dollar_volume: Decimal | None = None
    history_status: str = "pending"
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    metadata_json: dict[str, Any] = field(default_factory=dict)


class SymbolRegistryService:
    KRAKEN_BASE_ALIASES: dict[str, str] = {
        "XBT": "BTC",
        "XDG": "DOGE",
    }

    KRAKEN_QUOTE_ALIASES: dict[str, str] = {
        "ZUSD": "USD",
        "USD": "USD",
        "USDT": "USDT",
        "USDC": "USDC",
        "ZEUR": "EUR",
        "EUR": "EUR",
        "BTC": "BTC",
        "ETH": "ETH",
    }

    def seed(self, db: Session, seeds: list[SymbolRegistrySeed], *, seen_at: datetime | None = None) -> list[SymbolRegistry]:
        timestamp = seen_at or datetime.now(UTC)
        persisted: list[SymbolRegistry] = []
        deduped: dict[tuple[AssetClass, str], SymbolRegistrySeed] = {}

        for seed in seeds:
            normalized_symbol = self.normalize_symbol(seed.symbol, seed.asset_class)
            normalized_seed = SymbolRegistrySeed(
                symbol=normalized_symbol,
                asset_class=seed.asset_class,
                source=seed.source.strip().lower(),
                is_active=seed.is_active,
                is_tradable=seed.is_tradable,
                sector_or_category=seed.sector_or_category,
                avg_dollar_volume=seed.avg_dollar_volume,
                history_status=seed.history_status.strip().lower(),
                first_seen_at=seed.first_seen_at or timestamp,
                last_seen_at=seed.last_seen_at or timestamp,
                metadata_json=dict(seed.metadata_json or {}),
            )
            deduped[(normalized_seed.asset_class, normalized_seed.symbol)] = normalized_seed

        for asset_class, symbol in deduped:
            seed = deduped[(asset_class, symbol)]
            existing = (
                db.query(SymbolRegistry)
                .filter(
                    SymbolRegistry.asset_class == asset_class,
                    SymbolRegistry.symbol == symbol,
                )
                .one_or_none()
            )

            if existing is None:
                row = SymbolRegistry(
                    symbol=seed.symbol,
                    asset_class=seed.asset_class,
                    source=seed.source,
                    is_active=seed.is_active,
                    is_tradable=seed.is_tradable,
                    sector_or_category=seed.sector_or_category,
                    avg_dollar_volume=seed.avg_dollar_volume,
                    history_status=seed.history_status,
                    first_seen_at=seed.first_seen_at or timestamp,
                    last_seen_at=seed.last_seen_at or timestamp,
                    metadata_json=seed.metadata_json,
                )
                db.add(row)
                db.flush()
                persisted.append(row)
                continue

            existing.source = seed.source
            existing.is_active = seed.is_active
            existing.is_tradable = seed.is_tradable
            existing.sector_or_category = seed.sector_or_category
            existing.avg_dollar_volume = seed.avg_dollar_volume
            existing.history_status = seed.history_status
            existing.last_seen_at = seed.last_seen_at or timestamp
            existing.metadata_json = seed.metadata_json
            persisted.append(existing)

        return sorted(persisted, key=lambda row: (row.asset_class.value, row.symbol))

    def list_symbols(
        self,
        db: Session,
        *,
        asset_class: AssetClass | None = None,
        active_only: bool = False,
        tradable_only: bool = False,
    ) -> list[SymbolRegistry]:
        query = db.query(SymbolRegistry)
        if asset_class is not None:
            query = query.filter(SymbolRegistry.asset_class == asset_class)
        if active_only:
            query = query.filter(SymbolRegistry.is_active.is_(True))
        if tradable_only:
            query = query.filter(SymbolRegistry.is_tradable.is_(True))
        return query.order_by(SymbolRegistry.asset_class.asc(), SymbolRegistry.symbol.asc()).all()

    def build_stock_seeds(
        self,
        symbols: list[str],
        *,
        source: str,
        sector_by_symbol: dict[str, str] | None = None,
        avg_dollar_volume_by_symbol: dict[str, Decimal] | None = None,
        seen_at: datetime | None = None,
    ) -> list[SymbolRegistrySeed]:
        timestamp = seen_at or datetime.now(UTC)
        sectors = sector_by_symbol or {}
        dollar_volume = avg_dollar_volume_by_symbol or {}
        return [
            SymbolRegistrySeed(
                symbol=symbol,
                asset_class=AssetClass.STOCK,
                source=source,
                sector_or_category=sectors.get(symbol.upper()),
                avg_dollar_volume=dollar_volume.get(symbol.upper()),
                first_seen_at=timestamp,
                last_seen_at=timestamp,
            )
            for symbol in symbols
        ]

    def build_kraken_seeds(self, rows: list[dict[str, Any]], *, seen_at: datetime | None = None) -> list[SymbolRegistrySeed]:
        timestamp = seen_at or datetime.now(UTC)
        seeds: list[SymbolRegistrySeed] = []
        for row in rows:
            display_symbol = self.normalize_kraken_display_symbol(
                altname=str(row.get("altname") or row.get("wsname") or row.get("symbol") or "")
            )
            if not display_symbol:
                continue
            seeds.append(
                SymbolRegistrySeed(
                    symbol=display_symbol,
                    asset_class=AssetClass.CRYPTO,
                    source="kraken_csv",
                    sector_or_category="crypto",
                    metadata_json={
                        "provider_symbol": row.get("symbol"),
                        "altname": row.get("altname"),
                        "wsname": row.get("wsname"),
                        "base": row.get("base"),
                        "quote": row.get("quote"),
                    },
                    first_seen_at=timestamp,
                    last_seen_at=timestamp,
                )
            )
        return seeds

    def normalize_symbol(self, symbol: str, asset_class: AssetClass) -> str:
        normalized = symbol.strip().upper()
        if asset_class == AssetClass.CRYPTO:
            return self.normalize_kraken_display_symbol(normalized)
        return normalized

    def normalize_kraken_display_symbol(self, altname: str) -> str:
        raw = altname.strip().upper().replace("-", "/")
        if not raw:
            return raw
        if "/" in raw:
            base, quote = raw.split("/", 1)
            return f"{self._normalize_kraken_asset(base)}/{self._normalize_kraken_asset(quote, is_quote=True)}"

        quote_candidates = sorted(self.KRAKEN_QUOTE_ALIASES, key=len, reverse=True)
        for quote_candidate in quote_candidates:
            if raw.endswith(quote_candidate) and len(raw) > len(quote_candidate):
                base = raw[: -len(quote_candidate)]
                quote = quote_candidate
                return f"{self._normalize_kraken_asset(base)}/{self._normalize_kraken_asset(quote, is_quote=True)}"
        return raw

    def _normalize_kraken_asset(self, value: str, *, is_quote: bool = False) -> str:
        cleaned = value.strip().upper().lstrip("XZ")
        if is_quote:
            return self.KRAKEN_QUOTE_ALIASES.get(value.strip().upper(), cleaned)
        return self.KRAKEN_BASE_ALIASES.get(value.strip().upper(), cleaned)
