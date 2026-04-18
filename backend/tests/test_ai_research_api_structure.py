from __future__ import annotations

from app.api.routes.ai_research import router
from app.schemas.ai_research_api import AISnapshotInspectionOut, UniverseSnapshotListOut


def test_ai_research_router_and_schemas_exist() -> None:
    paths = {route.path for route in router.routes}
    assert "/api/ai/snapshots/latest" in paths
    assert "/api/ai/universe/latest" in paths
    assert AISnapshotInspectionOut is not None
    assert UniverseSnapshotListOut is not None
