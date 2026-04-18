from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.services.historical import AIResearchSchedulerService


class SequenceClock:
    def __init__(self, *values: datetime) -> None:
        self.values = list(values)
        self.index = 0

    def __call__(self) -> datetime:
        if self.index >= len(self.values):
            return self.values[-1]
        value = self.values[self.index]
        self.index += 1
        return value


@pytest.mark.asyncio
async def test_scheduler_runs_once_on_startup_then_waits_until_next_day() -> None:
    calls: list[str] = []

    async def fake_runner() -> dict[str, object]:
        calls.append("ran")
        return {"rows": 4}

    clock = SequenceClock(
        datetime(2026, 4, 18, 12, 0, tzinfo=UTC),
        datetime(2026, 4, 18, 12, 0, 1, tzinfo=UTC),
        datetime(2026, 4, 18, 12, 0, 2, tzinfo=UTC),
    )
    scheduler = AIResearchSchedulerService(
        timezone_name="America/New_York",
        daily_run_time="08:40",
        enabled=True,
        startup_run_enabled=True,
        run_research=fake_runner,
        now_provider=clock,
    )

    decision = scheduler.evaluate(datetime(2026, 4, 18, 12, 0, tzinfo=UTC))
    assert decision.should_run is True
    assert decision.reason == "startup_bootstrap"

    result = await scheduler.run_once(reason=decision.reason)
    status = scheduler.get_status()

    assert calls == ["ran"]
    assert result == {"reason": "startup_bootstrap", "rows": 4}
    assert status["last_run_local_date"] == "2026-04-18"
    assert status["last_result"] == {"reason": "startup_bootstrap", "rows": 4}
    assert status["next_scheduled_run_at"] == "2026-04-19T12:40:00+00:00"


@pytest.mark.asyncio
async def test_scheduler_runs_after_daily_cutoff_only_once_per_day() -> None:
    calls = 0

    async def fake_runner() -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"status": "ok"}

    clock = SequenceClock(
        datetime(2026, 4, 18, 12, 45, tzinfo=UTC),
        datetime(2026, 4, 18, 12, 45, 1, tzinfo=UTC),
        datetime(2026, 4, 18, 12, 45, 2, tzinfo=UTC),
    )
    scheduler = AIResearchSchedulerService(
        timezone_name="America/New_York",
        daily_run_time="08:40",
        enabled=True,
        startup_run_enabled=False,
        run_research=fake_runner,
        now_provider=clock,
    )

    decision = scheduler.evaluate(datetime(2026, 4, 18, 12, 45, tzinfo=UTC))
    assert decision.should_run is True
    assert decision.reason == "daily_schedule"

    await scheduler.run_once(reason=decision.reason)

    later_decision = scheduler.evaluate(datetime(2026, 4, 18, 13, 30, tzinfo=UTC))
    assert later_decision.should_run is False
    assert later_decision.reason == "already_ran_today"
    assert calls == 1


def test_scheduler_waits_for_0840_eastern_before_running_daily_job() -> None:
    scheduler = AIResearchSchedulerService(
        timezone_name="America/New_York",
        daily_run_time="08:40",
        enabled=True,
        startup_run_enabled=False,
        now_provider=lambda: datetime(2026, 4, 18, 12, 30, tzinfo=UTC),
    )

    decision = scheduler.evaluate(datetime(2026, 4, 18, 12, 30, tzinfo=UTC))

    assert decision.should_run is False
    assert decision.reason == "waiting_for_schedule"
    assert decision.scheduled_for == datetime(2026, 4, 18, 12, 40, tzinfo=UTC)
