from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import delete, select, tuple_
from sqlalchemy.orm import Session

from app.models.ai_research import HistoricalUniverseSnapshot, SymbolRegistry
from app.models.trading import AssetClass


class HistoricalUniverseSnapshotService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def freeze_from_symbol_registry(
        self,
        *,
        decision_date: date,
        asset_class: AssetClass,
        source_label: str,
        active_only: bool = True,
        tradable_only: bool = True,
    ) -> int:
        registry_rows = self._query_registry_rows(
            asset_class=asset_class,
            active_only=active_only,
            tradable_only=tradable_only,
        )

        key_tuples = [(decision_date, asset_class, row.symbol) for row in registry_rows]
        replaced = self._replace_existing(key_tuples)

        for row in registry_rows:
            self._session.add(
                HistoricalUniverseSnapshot(
                    decision_date=decision_date,
                    symbol=row.symbol,
                    asset_class=row.asset_class,
                    source_label=source_label,
                    registry_source=row.source,
                    is_active=row.is_active,
                    is_tradable=row.is_tradable,
                    history_status=row.history_status,
                    sector_or_category=row.sector_or_category,
                    avg_dollar_volume=row.avg_dollar_volume,
                    first_seen_at=_as_utc(row.first_seen_at),
                    last_seen_at=_as_utc(row.last_seen_at),
                    metadata_json=dict(row.metadata_json or {}),
                )
            )

        self._session.flush()
        return len(registry_rows)

    def list_symbols(
        self,
        *,
        decision_date: date,
        asset_class: AssetClass,
    ) -> list[HistoricalUniverseSnapshot]:
        statement = (
            select(HistoricalUniverseSnapshot)
            .where(
                HistoricalUniverseSnapshot.decision_date == decision_date,
                HistoricalUniverseSnapshot.asset_class == asset_class,
            )
            .order_by(HistoricalUniverseSnapshot.symbol.asc())
        )
        return list(self._session.scalars(statement))

    def _query_registry_rows(
        self,
        *,
        asset_class: AssetClass,
        active_only: bool,
        tradable_only: bool,
    ) -> list[SymbolRegistry]:
        statement = select(SymbolRegistry).where(SymbolRegistry.asset_class == asset_class)
        if active_only:
            statement = statement.where(SymbolRegistry.is_active.is_(True))
        if tradable_only:
            statement = statement.where(SymbolRegistry.is_tradable.is_(True))
        statement = statement.order_by(SymbolRegistry.symbol.asc())
        return list(self._session.scalars(statement))

    def _replace_existing(
        self,
        keys: list[tuple[date, AssetClass, str]],
    ) -> int:
        if not keys:
            return 0
        result = self._session.execute(
            delete(HistoricalUniverseSnapshot).where(
                tuple_(
                    HistoricalUniverseSnapshot.decision_date,
                    HistoricalUniverseSnapshot.asset_class,
                    HistoricalUniverseSnapshot.symbol,
                ).in_(keys)
            )
        )
        return int(result.rowcount or 0)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
