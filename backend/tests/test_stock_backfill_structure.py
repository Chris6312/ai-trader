from __future__ import annotations

from app.api.routes.ai_research import router
from app.schemas.stock_backfill_api import StockBackfillPolicyOut, StockBackfillTimeframePolicyOut
from app.services.historical import StockBackfillPolicy, StockBackfillPolicyService, StockBackfillTimeframePolicy


def test_stock_backfill_exports_and_route_exist() -> None:
    paths = {route.path for route in router.routes}

    assert "/api/ai/backfill/stocks/policy" in paths
    assert StockBackfillPolicyService is not None
    assert StockBackfillPolicy is not None
    assert StockBackfillTimeframePolicy is not None
    assert StockBackfillPolicyOut is not None
    assert StockBackfillTimeframePolicyOut is not None
