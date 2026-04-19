from __future__ import annotations

import pytest

from app.services.historical.stock_backfill_policy import StockBackfillPolicyService


def test_stock_backfill_policy_defaults_match_phase_12q_contract() -> None:
    service = StockBackfillPolicyService()

    policy = service.resolve_default_policy()

    assert policy.policy_version == "12q_stock_policy_v1"
    assert policy.policy_name == "ml_stock_history_defaults"
    assert policy.asset_class == "stock"
    assert policy.symbol_source == "active_registry"
    assert policy.max_symbols_per_run == 200
    assert policy.max_parallel_fetches == 5
    assert list(policy.timeframes.keys()) == ["15m", "1h", "4h", "1d"]
    assert policy.timeframes["15m"].lookback_days == 60
    assert policy.timeframes["15m"].lookback_label == "60 trading days"
    assert policy.timeframes["1h"].lookback_days == 180
    assert policy.timeframes["4h"].lookback_days == 365
    assert policy.timeframes["1d"].lookback_days == 730


@pytest.mark.parametrize(
    ("timeframe", "expected_days"),
    [("15m", 60), ("1h", 180), ("4h", 365), ("1d", 730)],
)
def test_stock_backfill_policy_resolves_lookback_days(timeframe: str, expected_days: int) -> None:
    service = StockBackfillPolicyService()

    assert service.resolve_lookback_days(timeframe) == expected_days


def test_stock_backfill_policy_rejects_unsupported_timeframe() -> None:
    service = StockBackfillPolicyService()

    with pytest.raises(ValueError, match="Unsupported stock backfill timeframe"):
        service.resolve_lookback_days("5m")
