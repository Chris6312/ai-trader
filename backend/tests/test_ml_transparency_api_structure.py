from __future__ import annotations

from app.api.routes.ai_research import router
from app.schemas.ai_research_api import (
    MLTransparencyExplanationOut,
    MLTransparencyModelRegistryOut,
    MLTransparencyOverviewOut,
    MLTransparencyRowListOut,
)


def test_ml_transparency_routes_and_schemas_exist() -> None:
    paths = {route.path for route in router.routes}
    assert "/api/ai/ml/models" in paths
    assert "/api/ai/ml/overview" in paths
    assert "/api/ai/ml/rows" in paths
    assert "/api/ai/ml/explanations/historical" in paths
    assert MLTransparencyModelRegistryOut is not None
    assert MLTransparencyOverviewOut is not None
    assert MLTransparencyRowListOut is not None
    assert MLTransparencyExplanationOut is not None
