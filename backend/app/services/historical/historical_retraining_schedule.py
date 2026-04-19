from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.services.historical.historical_retraining_schedule_schemas import (
    HistoricalRetrainingContext,
    HistoricalRetrainingScheduleConfig,
    HistoricalRetrainingScheduleSummary,
    RetrainingPipelineStep,
)


class HistoricalRetrainingScheduleService:
    def __init__(self, *, config: HistoricalRetrainingScheduleConfig | None = None) -> None:
        self._config = config or HistoricalRetrainingScheduleConfig()
        self._timezone = ZoneInfo(self._config.timezone_name)
        self._scheduled_time = self._parse_time(self._config.scheduled_time)

    def evaluate(self, context: HistoricalRetrainingContext) -> HistoricalRetrainingScheduleSummary:
        current = self._coerce_utc(context.now)
        scheduled_for = self._scheduled_for(current)
        new_rows_available = max(
            context.latest_row_count - int(context.active_dataset_row_count or 0),
            0,
        )
        drift_triggered = (
            self._config.force_retrain_on_drift
            and context.drifted_feature_count >= self._config.drifted_feature_threshold
        )
        validation_triggered = (
            self._config.force_retrain_on_validation_drop
            and context.last_validation_roc_auc is not None
            and context.last_validation_roc_auc < self._config.min_acceptable_roc_auc
        )

        should_retrain = False
        reason = "waiting_for_schedule"

        if context.manual_trigger:
            should_retrain = True
            reason = "manual_trigger"
        elif context.active_model_version is None:
            should_retrain = True
            reason = "bootstrap_missing_active_model"
        elif drift_triggered and new_rows_available >= self._config.min_new_rows:
            should_retrain = True
            reason = "drift_threshold_exceeded"
        elif validation_triggered and new_rows_available >= self._config.min_new_rows:
            should_retrain = True
            reason = "validation_below_floor"
        elif not self._is_schedule_due(current):
            should_retrain = False
            reason = "waiting_for_schedule"
        elif new_rows_available < self._config.min_new_rows:
            should_retrain = False
            reason = "insufficient_new_rows"
        elif not self._cooldown_met(current, context.active_model_trained_at):
            should_retrain = False
            reason = "cooldown_not_met"
        else:
            should_retrain = True
            reason = "scheduled_weekly_retrain"

        summary = HistoricalRetrainingScheduleSummary(
            schedule_version=self._build_schedule_version(
                context=context,
                scheduled_for=scheduled_for,
                new_rows_available=new_rows_available,
            ),
            should_retrain=should_retrain,
            reason=reason,
            cadence=self._config.cadence,
            strategy_name=context.latest_strategy_name,
            scheduled_for=scheduled_for,
            latest_dataset_version=context.latest_dataset_version,
            active_model_version=context.active_model_version,
            latest_row_count=context.latest_row_count,
            new_rows_available=new_rows_available,
            drift_triggered=drift_triggered,
            validation_triggered=validation_triggered,
            guardrails=self._build_guardrails(),
            pipeline_steps=self._build_pipeline_steps(),
        )
        return summary

    def _build_guardrails(self) -> list[str]:
        return [
            "ML retraining is ranking-only and cannot bypass deterministic eligibility or risk controls.",
            "New models must complete walk-forward validation before operator review.",
            "Retraining can stage a candidate model but cannot auto-promote it into execution authority.",
        ]

    def _build_pipeline_steps(self) -> list[RetrainingPipelineStep]:
        return [
            RetrainingPipelineStep(
                step_key="build_dataset",
                title="Build rolling dataset",
                required=True,
                description="Refresh the strategy-scoped historical dataset using only point-in-time rows newer than the active training window.",
            ),
            RetrainingPipelineStep(
                step_key="train_model",
                title="Train candidate model",
                required=True,
                description="Fit a new baseline model against the refreshed dataset with versioned hyperparameters.",
            ),
            RetrainingPipelineStep(
                step_key="walkforward_validation",
                title="Run walk-forward validation",
                required=True,
                description="Evaluate the candidate model on future-only validation windows before any promotion decision.",
            ),
            RetrainingPipelineStep(
                step_key="drift_review",
                title="Review importance and drift",
                required=True,
                description="Generate feature-importance and drift summaries so operators can inspect what changed.",
            ),
            RetrainingPipelineStep(
                step_key="stage_candidate",
                title="Stage for operator approval",
                required=True,
                description="Publish the candidate artifact and reports for approval without auto-promoting the model.",
            ),
        ]

    def _scheduled_for(self, now: datetime) -> datetime:
        local_now = now.astimezone(self._timezone)
        days_ahead = (self._config.scheduled_day_of_week - local_now.weekday()) % 7
        target_date = local_now.date() + timedelta(days=days_ahead)
        target_local = datetime.combine(target_date, self._scheduled_time, tzinfo=self._timezone)
        if days_ahead == 0 and local_now > target_local:
            target_local = target_local + timedelta(days=7)
        return target_local.astimezone(UTC)

    def _is_schedule_due(self, now: datetime) -> bool:
        local_now = now.astimezone(self._timezone)
        if local_now.weekday() != self._config.scheduled_day_of_week:
            return False
        target_local = datetime.combine(local_now.date(), self._scheduled_time, tzinfo=self._timezone)
        return local_now >= target_local

    def _cooldown_met(self, now: datetime, trained_at: datetime | None) -> bool:
        if trained_at is None:
            return True
        trained_utc = self._coerce_utc(trained_at)
        return now >= trained_utc + timedelta(days=self._config.min_days_between_runs)

    def _build_schedule_version(
        self,
        *,
        context: HistoricalRetrainingContext,
        scheduled_for: datetime,
        new_rows_available: int,
    ) -> str:
        payload = {
            "config": asdict(self._config),
            "context": asdict(context),
            "new_rows_available": new_rows_available,
            "scheduled_for": scheduled_for.isoformat(),
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=self._json_default).encode("utf-8")
        ).hexdigest()[:16]
        return f"{self._config.schedule_version_prefix}_{digest}"

    @staticmethod
    def _parse_time(raw_value: str) -> time:
        hours, minutes = raw_value.split(":", maxsplit=1)
        return time(hour=int(hours), minute=int(minutes))

    @staticmethod
    def _coerce_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _json_default(value: object) -> str:
        if isinstance(value, datetime | date):
            return value.isoformat()
        raise TypeError(f"Object of type {type(value)!r} is not JSON serializable")
