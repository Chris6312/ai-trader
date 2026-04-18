from __future__ import annotations

from datetime import UTC, datetime

from app.services.historical.backfill_planner import BackfillPlanner


def test_plan_incremental_uses_bootstrap_when_history_is_empty() -> None:
    planner = BackfillPlanner()
    bootstrap_start_at = datetime(2026, 1, 1, tzinfo=UTC)
    requested_end_at = datetime(2026, 4, 18, tzinfo=UTC)

    plan = planner.plan_incremental(
        symbol="AAPL",
        asset_class="stock",
        timeframe="1d",
        latest_candle_ts=None,
        bootstrap_start_at=bootstrap_start_at,
        requested_end_at=requested_end_at,
    )

    assert plan.should_fetch is True
    assert plan.reason == "empty_history"
    assert plan.fetch_start_at == bootstrap_start_at
    assert plan.fetch_end_at == requested_end_at


def test_plan_incremental_advances_from_latest_timestamp() -> None:
    planner = BackfillPlanner()
    latest_candle_ts = datetime(2026, 4, 17, 0, 0, tzinfo=UTC)
    requested_end_at = datetime(2026, 4, 20, 0, 0, tzinfo=UTC)

    plan = planner.plan_incremental(
        symbol="AAPL",
        asset_class="stock",
        timeframe="1d",
        latest_candle_ts=latest_candle_ts,
        requested_end_at=requested_end_at,
    )

    assert plan.should_fetch is True
    assert plan.reason == "incremental_gap"
    assert plan.fetch_start_at == datetime(2026, 4, 18, 0, 0, tzinfo=UTC)
    assert plan.fetch_end_at == requested_end_at


def test_plan_incremental_returns_already_current_when_no_gap_exists() -> None:
    planner = BackfillPlanner()
    latest_candle_ts = datetime(2026, 4, 18, 12, 0, tzinfo=UTC)
    requested_end_at = datetime(2026, 4, 18, 12, 15, tzinfo=UTC)

    plan = planner.plan_incremental(
        symbol="BTC/USD",
        asset_class="crypto",
        timeframe="15m",
        latest_candle_ts=latest_candle_ts,
        requested_end_at=requested_end_at,
    )

    assert plan.should_fetch is False
    assert plan.reason == "already_current"
    assert plan.fetch_start_at == requested_end_at


def test_plan_incremental_requires_bootstrap_for_empty_history() -> None:
    planner = BackfillPlanner()
    requested_end_at = datetime(2026, 4, 18, tzinfo=UTC)

    plan = planner.plan_incremental(
        symbol="MSFT",
        asset_class="stock",
        timeframe="1h",
        latest_candle_ts=None,
        requested_end_at=requested_end_at,
    )

    assert plan.should_fetch is False
    assert plan.reason == "missing_bootstrap_start"
    assert plan.fetch_start_at is None
