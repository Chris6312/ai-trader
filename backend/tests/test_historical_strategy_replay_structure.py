from __future__ import annotations

from app.services.historical import HistoricalReplayPolicy, HistoricalReplayRecord, HistoricalReplaySummary, HistoricalStrategyReplayService
from app.services.historical.historical_replay_schemas import (
    HistoricalReplayPolicy as DirectHistoricalReplayPolicy,
)
from app.services.historical.historical_replay_schemas import (
    HistoricalReplayRecord as DirectHistoricalReplayRecord,
)
from app.services.historical.historical_replay_schemas import (
    HistoricalReplaySummary as DirectHistoricalReplaySummary,
)
from app.services.historical.historical_strategy_replay import HistoricalStrategyReplayService as DirectHistoricalStrategyReplayService


def test_historical_strategy_replay_exports_are_available_from_package() -> None:
    assert HistoricalStrategyReplayService is DirectHistoricalStrategyReplayService
    assert HistoricalReplayPolicy is DirectHistoricalReplayPolicy
    assert HistoricalReplayRecord is DirectHistoricalReplayRecord
    assert HistoricalReplaySummary is DirectHistoricalReplaySummary


def test_historical_strategy_replay_uses_phase_12c_replay_version() -> None:
    assert HistoricalStrategyReplayService.REPLAY_VERSION == "12c_v1"
