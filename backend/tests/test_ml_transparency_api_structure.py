from __future__ import annotations

from app.api.routes.ai_research import router
from app.schemas.ai_research_api import (
    MLBundleBuildOut,
    MLBundleBuildRequest,
    MLDeploymentActionOut,
    MLDeploymentStateOut,
    MLTransparencyExplanationOut,
    MLTransparencyFeatureHealthPanelOut,
    MLTransparencyModelRegistryOut,
    MLTransparencyOverviewOut,
    MLTransparencyStrategyLearningPanelOut,
    MLTransparencyRowListOut,
)


def test_ml_transparency_routes_and_schemas_exist() -> None:
    paths = {route.path for route in router.routes}
    assert "/api/ai/ml/bundles/build" in paths
    assert "/api/ai/ml/deployment/state" in paths
    assert "/api/ai/ml/deployment/approve/{bundle_version}" in paths
    assert "/api/ai/ml/deployment/promote/{bundle_version}" in paths
    assert "/api/ai/ml/deployment/rollback" in paths
    assert "/api/ai/ml/deployment/freeze/{bundle_version}" in paths
    assert "/api/ai/ml/deployment/unfreeze" in paths
    assert "/api/ai/ml/models" in paths
    assert "/api/ai/ml/overview" in paths
    assert "/api/ai/ml/rows" in paths
    assert "/api/ai/ml/inspection/strategy" in paths
    assert "/api/ai/ml/inspection/feature-health" in paths
    assert "/api/ai/ml/explanations/by-symbol-date" in paths
    assert "/api/ai/ml/explanations/historical" in paths
    assert MLBundleBuildRequest is not None
    assert MLBundleBuildOut is not None
    assert MLDeploymentStateOut is not None
    assert MLDeploymentActionOut is not None
    assert MLTransparencyModelRegistryOut is not None
    assert MLTransparencyOverviewOut is not None
    assert MLTransparencyRowListOut is not None
    assert MLTransparencyStrategyLearningPanelOut is not None
    assert MLTransparencyFeatureHealthPanelOut is not None
    assert MLTransparencyExplanationOut is not None
