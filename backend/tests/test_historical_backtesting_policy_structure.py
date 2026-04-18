from app.services.historical import (
    BacktestingPolicyVersionRecord,
    HistoricalBacktestingPolicy,
    HistoricalBacktestingPolicyService,
    ResolvedBacktestingPolicyRecord,
)


def test_historical_backtesting_policy_exports_are_available() -> None:
    assert HistoricalBacktestingPolicy is not None
    assert BacktestingPolicyVersionRecord is not None
    assert ResolvedBacktestingPolicyRecord is not None
    assert HistoricalBacktestingPolicyService is not None
