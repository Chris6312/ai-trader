from app.services.historical import AIResearchSchedulerService
from app.services.historical.ai_scheduler import AIResearchSchedulerService as DirectAIResearchSchedulerService


def test_ai_scheduler_exports_are_available_from_package() -> None:
    assert AIResearchSchedulerService is DirectAIResearchSchedulerService


def test_ai_scheduler_status_shape_contains_daily_runtime_fields() -> None:
    service = AIResearchSchedulerService(enabled=False)
    status = service.get_status()

    assert status["enabled"] is False
    assert status["daily_run_time"] == "08:40"
    assert "next_scheduled_run_at" in status
    assert "last_run_local_date" in status
