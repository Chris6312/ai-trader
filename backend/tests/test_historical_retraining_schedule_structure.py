from __future__ import annotations

from app.services.historical import (
    HistoricalRetrainingContext,
    HistoricalRetrainingScheduleConfig,
    HistoricalRetrainingScheduleService,
    HistoricalRetrainingScheduleSummary,
    RetrainingPipelineStep,
)
from app.services.historical.historical_retraining_schedule import HistoricalRetrainingScheduleService as DirectService
from app.services.historical.historical_retraining_schedule_schemas import (
    HistoricalRetrainingScheduleConfig as DirectConfig,
)


def test_retraining_schedule_exports_are_available() -> None:
    assert HistoricalRetrainingScheduleService is DirectService
    assert HistoricalRetrainingScheduleConfig is DirectConfig
    assert HistoricalRetrainingContext is not None
    assert HistoricalRetrainingScheduleSummary is not None
    assert RetrainingPipelineStep is not None



def test_retraining_schedule_defaults_match_phase_12k_foundation() -> None:
    config = HistoricalRetrainingScheduleConfig()

    assert config.schedule_version_prefix == "12k_v1"
    assert config.cadence == "weekly"
    assert config.timezone_name == "America/New_York"
    assert config.scheduled_time == "08:40"
