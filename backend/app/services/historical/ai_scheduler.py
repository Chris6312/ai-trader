from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Awaitable, Callable
from zoneinfo import ZoneInfo


RunResearchCallable = Callable[[], Awaitable[dict[str, object] | None]]
NowCallable = Callable[[], datetime]


@dataclass(slots=True)
class AISchedulerDecision:
    should_run: bool
    reason: str
    scheduled_for: datetime


class AIResearchSchedulerService:
    def __init__(
        self,
        *,
        timezone_name: str = "America/New_York",
        daily_run_time: str = "08:40",
        enabled: bool = False,
        startup_run_enabled: bool = True,
        run_research: RunResearchCallable | None = None,
        now_provider: NowCallable | None = None,
        sleep_seconds: float = 30.0,
    ) -> None:
        self.timezone = ZoneInfo(timezone_name)
        self.daily_run_time = self._parse_daily_run_time(daily_run_time)
        self.enabled = enabled
        self.startup_run_enabled = startup_run_enabled
        self._run_research = run_research or self._noop_run_research
        self._now_provider = now_provider or (lambda: datetime.now(UTC))
        self._sleep_seconds = sleep_seconds

        self._last_started_at: datetime | None = None
        self._last_finished_at: datetime | None = None
        self._last_succeeded_at: datetime | None = None
        self._last_error: str | None = None
        self._last_result: dict[str, object] | None = None
        self._last_run_local_date: date | None = None
        self._next_scheduled_run_at: datetime | None = None
        self._running = False
        self._stop_requested = False
        self._stop_event = asyncio.Event()

    async def run(self) -> None:
        self._running = True
        self._stop_requested = False
        self._stop_event.clear()
        try:
            while not self._stop_requested:
                decision = self.evaluate(self.now())
                self._next_scheduled_run_at = decision.scheduled_for
                if decision.should_run:
                    await self._execute_run(reason=decision.reason)
                    continue
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=self._sleep_seconds)
                except asyncio.TimeoutError:
                    continue
        finally:
            self._running = False
            self._next_scheduled_run_at = None

    def stop(self) -> None:
        self._stop_requested = True
        self._stop_event.set()

    def evaluate(self, now: datetime | None = None) -> AISchedulerDecision:
        current = self._coerce_utc(now or self.now())
        local_now = current.astimezone(self.timezone)
        scheduled_for = self.next_run_at(current)

        if not self.enabled:
            return AISchedulerDecision(False, "disabled", scheduled_for)

        if self.startup_run_enabled and self._last_run_local_date is None:
            return AISchedulerDecision(True, "startup_bootstrap", local_now.astimezone(UTC))

        if self._last_run_local_date == local_now.date():
            return AISchedulerDecision(False, "already_ran_today", scheduled_for)

        target_local = datetime.combine(local_now.date(), self.daily_run_time, tzinfo=self.timezone)
        target_utc = target_local.astimezone(UTC)
        if current >= target_utc:
            return AISchedulerDecision(True, "daily_schedule", target_utc)

        return AISchedulerDecision(False, "waiting_for_schedule", target_utc)

    def next_run_at(self, now: datetime | None = None) -> datetime:
        current = self._coerce_utc(now or self.now())
        local_now = current.astimezone(self.timezone)
        target_local = datetime.combine(local_now.date(), self.daily_run_time, tzinfo=self.timezone)

        if not self.enabled:
            return target_local.astimezone(UTC)

        if self.startup_run_enabled and self._last_run_local_date is None:
            return current

        if self._last_run_local_date == local_now.date():
            target_local = target_local + timedelta(days=1)
        elif local_now >= target_local:
            target_local = local_now

        return target_local.astimezone(UTC)

    async def run_once(self, *, reason: str = "manual") -> dict[str, object] | None:
        return await self._execute_run(reason=reason)

    def get_status(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "startup_run_enabled": self.startup_run_enabled,
            "running": self._running,
            "timezone": self.timezone.key,
            "daily_run_time": self.daily_run_time.strftime("%H:%M"),
            "last_started_at": self._iso(self._last_started_at),
            "last_finished_at": self._iso(self._last_finished_at),
            "last_succeeded_at": self._iso(self._last_succeeded_at),
            "last_run_local_date": self._last_run_local_date.isoformat() if self._last_run_local_date else None,
            "last_error": self._last_error,
            "last_result": self._last_result,
            "next_scheduled_run_at": self._iso(self._next_scheduled_run_at or self.next_run_at()),
        }

    def now(self) -> datetime:
        return self._coerce_utc(self._now_provider())

    async def _execute_run(self, *, reason: str) -> dict[str, object] | None:
        started_at = self.now()
        self._last_started_at = started_at
        self._last_error = None

        try:
            payload = await self._run_research()
        except Exception as exc:
            self._last_finished_at = self.now()
            self._last_error = f"{type(exc).__name__}: {exc}"
            raise

        finished_at = self.now()
        local_finished = finished_at.astimezone(self.timezone)
        result = {"reason": reason}
        if payload:
            result.update(payload)

        self._last_finished_at = finished_at
        self._last_succeeded_at = finished_at
        self._last_run_local_date = local_finished.date()
        self._last_result = result
        self._next_scheduled_run_at = self.next_run_at(finished_at)
        return result

    @staticmethod
    async def _noop_run_research() -> dict[str, object]:
        return {"status": "noop"}

    @staticmethod
    def _parse_daily_run_time(raw_value: str) -> time:
        pieces = raw_value.split(":")
        if len(pieces) != 2:
            raise ValueError("daily_run_time must use HH:MM format")
        hour = int(pieces[0])
        minute = int(pieces[1])
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise ValueError("daily_run_time must use a valid 24-hour clock time")
        return time(hour=hour, minute=minute)

    @staticmethod
    def _coerce_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _iso(value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.astimezone(UTC).isoformat()