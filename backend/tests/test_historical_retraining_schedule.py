from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, date, datetime

from app.services.historical.historical_retraining_schedule import HistoricalRetrainingScheduleService
from app.services.historical.historical_retraining_schedule_schemas import (
    HistoricalRetrainingContext,
    HistoricalRetrainingScheduleConfig,
)


def _build_context(**overrides: object) -> HistoricalRetrainingContext:
    base = HistoricalRetrainingContext(
        now=datetime(2026, 4, 18, 13, 0, tzinfo=UTC),
        latest_dataset_version="12f_dataset_v2",
        latest_dataset_end_date=date(2026, 4, 17),
        latest_row_count=180,
        latest_strategy_name="momentum",
        active_model_version="12g_model_v1",
        active_dataset_version="12f_dataset_v1",
        active_dataset_end_date=date(2026, 4, 10),
        active_dataset_row_count=120,
        active_model_trained_at=datetime(2026, 4, 10, 12, 0, tzinfo=UTC),
        last_validation_version="12h_v1_foldset",
        last_validation_roc_auc=0.61,
        last_drift_report_version="12i_v1_review",
        drifted_feature_count=1,
        manual_trigger=False,
    )
    values = asdict(base) | overrides
    return HistoricalRetrainingContext(**values)


def test_retraining_schedule_runs_on_due_weekly_window() -> None:
    service = HistoricalRetrainingScheduleService(
        config=HistoricalRetrainingScheduleConfig(
            scheduled_day_of_week=5,
            scheduled_time="08:40",
            min_days_between_runs=7,
            min_new_rows=20,
        )
    )

    summary = service.evaluate(_build_context())

    assert summary.should_retrain is True
    assert summary.reason == "scheduled_weekly_retrain"
    assert summary.new_rows_available == 60
    assert summary.pipeline_steps
    assert summary.pipeline_steps[0].step_key == "build_dataset"



def test_retraining_schedule_can_trigger_early_on_drift() -> None:
    service = HistoricalRetrainingScheduleService(
        config=HistoricalRetrainingScheduleConfig(
            scheduled_day_of_week=6,
            scheduled_time="08:40",
            min_new_rows=20,
            drifted_feature_threshold=2,
        )
    )

    summary = service.evaluate(
        _build_context(
            now=datetime(2026, 4, 15, 13, 0, tzinfo=UTC),
            drifted_feature_count=3,
        )
    )

    assert summary.should_retrain is True
    assert summary.reason == "drift_threshold_exceeded"
    assert summary.drift_triggered is True



def test_retraining_schedule_respects_minimum_new_rows_guardrail() -> None:
    service = HistoricalRetrainingScheduleService(
        config=HistoricalRetrainingScheduleConfig(
            scheduled_day_of_week=5,
            scheduled_time="08:40",
            min_new_rows=100,
        )
    )

    summary = service.evaluate(_build_context())

    assert summary.should_retrain is False
    assert summary.reason == "insufficient_new_rows"



def test_retraining_schedule_is_deterministic_for_same_inputs() -> None:
    service = HistoricalRetrainingScheduleService()
    context = _build_context()

    first = service.evaluate(context)
    second = service.evaluate(context)

    assert first.schedule_version == second.schedule_version
    assert first.scheduled_for == second.scheduled_for
    assert first.pipeline_steps == second.pipeline_steps
