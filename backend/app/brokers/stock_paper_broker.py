from __future__ import annotations

from decimal import Decimal

from app.brokers.paper_engine import BasePaperBroker
from app.models import AssetClass


class StockPaperBroker(BasePaperBroker):
    def __init__(
        self,
        *,
        initial_cash: Decimal,
        base_currency: str = "USD",
        fee_rate: Decimal = Decimal("0"),
    ) -> None:
        super().__init__(
            asset_class=AssetClass.STOCK,
            initial_cash=initial_cash,
            base_currency=base_currency,
            fee_rate=fee_rate,
        )
