from __future__ import annotations

from app.api.routes.ai_research import router
from app.schemas.ai_research_api import MLRuntimeControlOut
from app.services.historical.historical_ml_runtime_controls import HistoricalMLRuntimeControlService
from app.services.historical.historical_ml_runtime_controls_schemas import (
    HistoricalMLRuntimeControlConfig,
    HistoricalMLRuntimeControlSummary,
)


def test_ml_runtime_control_routes_and_schemas_exist() -> None:
    paths = {route.path for route in router.routes}
    assert "/api/ai/ml/runtime" in paths
    assert HistoricalMLRuntimeControlService is not None
    assert HistoricalMLRuntimeControlConfig is not None
    assert HistoricalMLRuntimeControlSummary is not None
    assert MLRuntimeControlOut is not None
