from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import AssetClass
from app.risk.approval import DeterministicRiskApprovalService
from app.risk.types import RiskApprovalRejection
from app.services.historical.historical_replay_schemas import HistoricalReplayPolicy
from app.services.historical.historical_strategy_replay import HistoricalStrategyReplayService
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
        ],
        seen_at=seen_at,
    )
    snapshot_service.freeze_from_symbol_registry(
        decision_date=seen_at.date(),
        asset_class=AssetClass.STOCK,
        source_label="phase12c_test",
    )
    session.commit()


def _build_candles(symbol: str) -> list[HistoricalCandleRecord]:
    start = datetime(2026, 4, 17, 0, 0, tzinfo=UTC)
    candles: list[HistoricalCandleRecord] = []
    for index in range(26):
        close = Decimal(100 + index)
        if index >= 24:
            close = Decimal(140 + (index - 24) * 6)
        candles.append(
            HistoricalCandleRecord(
                symbol=symbol,
                asset_class="stock",
                timeframe="1h",
                candle_time=start + timedelta(hours=index),
                open=close - Decimal("1"),
                high=close + Decimal("3"),
                low=close - Decimal("2"),
                close=close,
                volume=Decimal(1000 + index * 25),
                source_label="alpaca",
                fetched_at=start + timedelta(days=2),
                retention_bucket="intraday_medium",
            )
        )
    return candles


def test_historical_strategy_replay_builds_and_persists_target_hit_trade() -> None:
    session = _build_session()
    seen_at = datetime(2026, 4, 18, 12, 0, tzinfo=UTC)
    _seed_universe(session, seen_at=seen_at)
    service = HistoricalStrategyReplayService(session)

    summary = service.replay_for_decision_date(
        decision_date=seen_at.date(),
        asset_class="stock",
        timeframe="1h",
        source_label="alpaca",
        strategy_names=["momentum"],
        candles_by_symbol={
            "AAPL": _build_candles("AAPL"),
            "MSFT": _build_candles("MSFT"),
        },
    )
    session.commit()

    rows = service.list_rows(decision_date=seen_at.date(), asset_class="stock", timeframe="1h")

    assert summary.symbols_requested == 1
    assert summary.entries_evaluated == 1
    assert summary.entries_approved == 1
    assert summary.trades_persisted == 1
    assert len(rows) == 1
    assert rows[0].symbol == "AAPL"
    assert rows[0].strategy_name == "momentum"
    assert rows[0].exit_reason == "target_hit"
    assert rows[0].gross_return > Decimal("0")


def test_historical_strategy_replay_replaces_existing_rows_deterministically() -> None:
    session = _build_session()
    seen_at = datetime(2026, 4, 18, 12, 0, tzinfo=UTC)
    _seed_universe(session, seen_at=seen_at)
    service = HistoricalStrategyReplayService(session)
    candles = {"AAPL": _build_candles("AAPL")}

    first = service.replay_for_decision_date(
        decision_date=seen_at.date(),
        asset_class="stock",
        timeframe="1h",
        source_label="alpaca",
        strategy_names=["momentum"],
        candles_by_symbol=candles,
    )
    session.commit()
    second = service.replay_for_decision_date(
        decision_date=seen_at.date(),
        asset_class="stock",
        timeframe="1h",
        source_label="alpaca",
        strategy_names=["momentum"],
        candles_by_symbol=candles,
    )
    session.commit()

    rows = service.list_rows(decision_date=seen_at.date(), asset_class="stock", timeframe="1h")

    assert first.trades_persisted == 1
    assert second.rows_replaced == 1
    assert len(rows) == 1
    assert rows[0].replay_version == "12c_v1"
    assert rows[0].policy_version == "12c_policy_v1"


class _AlwaysRejectRiskApprovalService(DeterministicRiskApprovalService):
    def approve(self, approval_input):  # type: ignore[override]
        result = super().approve(approval_input)
        return type(result)(
            symbol=result.symbol,
            asset_class=result.asset_class,
            approved=False,
            rejection_reason=RiskApprovalRejection.MAX_OPEN_POSITIONS_EXCEEDED,
            reasoning=result.reasoning,
        )


def test_historical_strategy_replay_skips_persistence_when_risk_rejects() -> None:
    session = _build_session()
    seen_at = datetime(2026, 4, 18, 12, 0, tzinfo=UTC)
    _seed_universe(session, seen_at=seen_at)
    policy = HistoricalReplayPolicy(
        policy_version="12c_policy_v1",
        target_r_multiple=Decimal("2"),
        max_hold_bars=5,
    )
    service = HistoricalStrategyReplayService(
        session,
        risk_service=_AlwaysRejectRiskApprovalService(),
        policy=policy,
    )

    summary = service.replay_for_decision_date(
        decision_date=seen_at.date(),
        asset_class="stock",
        timeframe="1h",
        source_label="alpaca",
        strategy_names=["momentum"],
        candles_by_symbol={"AAPL": _build_candles("AAPL")},
    )
    session.commit()

    rows = service.list_rows(decision_date=seen_at.date(), asset_class="stock", timeframe="1h")
    assert summary.entries_evaluated == 1
    assert summary.entries_approved == 0
    assert summary.trades_persisted == 0
    assert rows == []
