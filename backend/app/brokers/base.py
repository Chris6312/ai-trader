from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal

from app.models import OrderStatus

from app.brokers.paper_models import (
    AccountSnapshot,
    BalanceSnapshot,
    FillSnapshot,
    OrderRequest,
    OrderSnapshot,
    PositionSnapshot,
)


class BrokerInterface(ABC):
    @abstractmethod
    def get_account_snapshot(self) -> AccountSnapshot:
        raise NotImplementedError

    @abstractmethod
    def get_balance(self) -> BalanceSnapshot:
        raise NotImplementedError

    @abstractmethod
    def list_orders(self, status: OrderStatus | None = None) -> list[OrderSnapshot]:
        raise NotImplementedError

    @abstractmethod
    def list_positions(self) -> list[PositionSnapshot]:
        raise NotImplementedError

    @abstractmethod
    def list_fills(self) -> list[FillSnapshot]:
        raise NotImplementedError

    @abstractmethod
    def place_order(
        self,
        request: OrderRequest,
        *,
        fill_price: Decimal | None = None,
        submitted_at: datetime | None = None,
    ) -> OrderSnapshot:
        raise NotImplementedError

    @abstractmethod
    def cancel_order(self, order_id: str, *, canceled_at: datetime | None = None) -> OrderSnapshot:
        raise NotImplementedError

    @abstractmethod
    def process_price_update(
        self,
        symbol: str,
        price: Decimal,
        *,
        as_of: datetime | None = None,
    ) -> list[FillSnapshot]:
        raise NotImplementedError
