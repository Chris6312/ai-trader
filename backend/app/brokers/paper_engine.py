from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.brokers.base import BrokerInterface
from app.brokers.paper_models import (
    AccountSnapshot,
    BalanceSnapshot,
    BrokerError,
    FillReason,
    FillSnapshot,
    InsufficientFundsError,
    InsufficientPositionError,
    InvalidOrderError,
    OrderNotFoundError,
    OrderRequest,
    OrderSnapshot,
    PositionSnapshot,
    build_fill_id,
    build_order_id,
    quantize_decimal,
)
from app.models import AssetClass, OrderSide, OrderStatus, OrderType


ZERO = Decimal("0")


class BasePaperBroker(BrokerInterface):
    def __init__(
        self,
        *,
        asset_class: AssetClass,
        initial_cash: Decimal,
        base_currency: str = "USD",
        fee_rate: Decimal = ZERO,
    ) -> None:
        self.asset_class = asset_class
        self.base_currency = base_currency
        self.fee_rate = quantize_decimal(fee_rate)
        cash_total = quantize_decimal(initial_cash)
        self._balance = BalanceSnapshot(
            currency=base_currency,
            total=cash_total,
            available=cash_total,
            reserved=ZERO,
        )
        self._orders: dict[str, OrderSnapshot] = {}
        self._positions: dict[str, PositionSnapshot] = {}
        self._fills: list[FillSnapshot] = []
        self._last_prices: dict[str, Decimal] = {}
        self._realized_pnl = ZERO

    def get_account_snapshot(self) -> AccountSnapshot:
        unrealized_pnl = quantize_decimal(sum((position.unrealized_pnl for position in self._positions.values()), start=ZERO))
        equity = quantize_decimal(self._balance.total + sum((position.market_value for position in self._positions.values()), start=ZERO))
        updated_at = self._balance.updated_at
        return AccountSnapshot(
            asset_class=self.asset_class,
            base_currency=self.base_currency,
            cash_total=self._balance.total,
            cash_available=self._balance.available,
            cash_reserved=self._balance.reserved,
            equity=equity,
            realized_pnl=quantize_decimal(self._realized_pnl),
            unrealized_pnl=unrealized_pnl,
            open_order_count=sum(1 for order in self._orders.values() if order.status is OrderStatus.OPEN),
            position_count=len(self._positions),
            updated_at=updated_at,
        )

    def get_balance(self) -> BalanceSnapshot:
        return BalanceSnapshot(
            currency=self._balance.currency,
            total=self._balance.total,
            available=self._balance.available,
            reserved=self._balance.reserved,
            updated_at=self._balance.updated_at,
        )

    def list_orders(self, status: OrderStatus | None = None) -> list[OrderSnapshot]:
        orders = list(self._orders.values())
        if status is not None:
            orders = [order for order in orders if order.status is status]
        return sorted(orders, key=lambda item: item.created_at)

    def list_positions(self) -> list[PositionSnapshot]:
        return sorted(self._positions.values(), key=lambda item: item.symbol)

    def list_fills(self) -> list[FillSnapshot]:
        return list(self._fills)

    def place_order(
        self,
        request: OrderRequest,
        *,
        fill_price: Decimal | None = None,
        submitted_at: datetime | None = None,
    ) -> OrderSnapshot:
        self._validate_order_request(request)

        timestamp = submitted_at or datetime.now(UTC)
        order = OrderSnapshot(
            id=build_order_id(self.asset_class),
            symbol=request.symbol.upper(),
            asset_class=self.asset_class,
            side=request.side,
            order_type=request.order_type,
            quantity=quantize_decimal(request.quantity),
            status=OrderStatus.OPEN,
            created_at=timestamp,
            updated_at=timestamp,
            limit_price=self._normalize_optional_decimal(request.limit_price),
            stop_price=self._normalize_optional_decimal(request.stop_price),
        )

        if order.side is OrderSide.BUY:
            order.reserved_cash = self._reserve_cash_for_order(order, fill_price=fill_price)
        else:
            order.reserved_quantity = self._reserve_position_for_order(order)

        self._orders[order.id] = order

        if order.order_type is OrderType.MARKET:
            execution_price = fill_price or self._last_prices.get(order.symbol)
            if execution_price is None:
                raise InvalidOrderError("Market orders require a fill_price or a known market price.")
            self._fill_order(order, execution_price=execution_price, reason=FillReason.MARKET, filled_at=timestamp)

        return order

    def cancel_order(self, order_id: str, *, canceled_at: datetime | None = None) -> OrderSnapshot:
        order = self._orders.get(order_id)
        if order is None:
            raise OrderNotFoundError(f"Unknown order id: {order_id}")
        if order.status is not OrderStatus.OPEN:
            raise BrokerError(f"Only open orders can be canceled. Order status is {order.status.value}.")

        if order.side is OrderSide.BUY:
            self._release_reserved_cash(order.reserved_cash)
            order.reserved_cash = ZERO
        else:
            self._release_reserved_quantity(order.symbol, order.reserved_quantity)
            order.reserved_quantity = ZERO

        order.status = OrderStatus.CANCELED
        order.updated_at = canceled_at or datetime.now(UTC)
        return order

    def process_price_update(
        self,
        symbol: str,
        price: Decimal,
        *,
        as_of: datetime | None = None,
    ) -> list[FillSnapshot]:
        normalized_symbol = symbol.upper()
        normalized_price = quantize_decimal(price)
        timestamp = as_of or datetime.now(UTC)
        self._last_prices[normalized_symbol] = normalized_price

        if normalized_symbol in self._positions:
            self._mark_position(normalized_symbol, normalized_price, timestamp)

        fills: list[FillSnapshot] = []
        for order in self.list_orders(status=OrderStatus.OPEN):
            if order.symbol != normalized_symbol:
                continue
            if self._should_fill_order(order, normalized_price):
                reason = self._resolve_fill_reason(order)
                fills.append(self._fill_order(order, execution_price=normalized_price, reason=reason, filled_at=timestamp))

        return fills

    def _validate_order_request(self, request: OrderRequest) -> None:
        symbol = request.symbol.strip().upper()
        if not symbol:
            raise InvalidOrderError("Order symbol is required.")
        if request.quantity <= ZERO:
            raise InvalidOrderError("Order quantity must be greater than zero.")

        if request.order_type is OrderType.LIMIT and request.limit_price is None:
            raise InvalidOrderError("Limit orders require a limit_price.")
        if request.order_type is OrderType.STOP and request.stop_price is None:
            raise InvalidOrderError("Stop orders require a stop_price.")
        if request.order_type is OrderType.STOP_LIMIT and (request.limit_price is None or request.stop_price is None):
            raise InvalidOrderError("Stop-limit orders require both stop_price and limit_price.")

    def _normalize_optional_decimal(self, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        return quantize_decimal(value)

    def _reserve_cash_for_order(self, order: OrderSnapshot, *, fill_price: Decimal | None) -> Decimal:
        price_basis = self._reservation_price(order, fill_price=fill_price)
        fee_estimate = self._calculate_fee(order.quantity, price_basis)
        reservation = quantize_decimal((order.quantity * price_basis) + fee_estimate)
        if reservation > self._balance.available:
            raise InsufficientFundsError(
                f"Insufficient available {self.base_currency}. Required={reservation}, available={self._balance.available}."
            )
        self._balance.available = quantize_decimal(self._balance.available - reservation)
        self._balance.reserved = quantize_decimal(self._balance.reserved + reservation)
        self._balance.updated_at = order.created_at
        return reservation

    def _reserve_position_for_order(self, order: OrderSnapshot) -> Decimal:
        position = self._positions.get(order.symbol)
        if position is None or position.quantity - position.reserved_quantity < order.quantity:
            available_quantity = ZERO if position is None else quantize_decimal(position.quantity - position.reserved_quantity)
            raise InsufficientPositionError(
                f"Insufficient available position quantity for {order.symbol}. Required={order.quantity}, available={available_quantity}."
            )
        position.reserved_quantity = quantize_decimal(position.reserved_quantity + order.quantity)
        position.updated_at = order.created_at
        return order.quantity

    def _release_reserved_cash(self, amount: Decimal) -> None:
        self._balance.reserved = quantize_decimal(self._balance.reserved - amount)
        self._balance.available = quantize_decimal(self._balance.available + amount)
        self._balance.updated_at = datetime.now(UTC)

    def _release_reserved_quantity(self, symbol: str, quantity: Decimal) -> None:
        position = self._positions[symbol]
        position.reserved_quantity = quantize_decimal(position.reserved_quantity - quantity)
        position.updated_at = datetime.now(UTC)

    def _reservation_price(self, order: OrderSnapshot, *, fill_price: Decimal | None) -> Decimal:
        if order.order_type is OrderType.MARKET:
            if fill_price is not None:
                return quantize_decimal(fill_price)
            last_price = self._last_prices.get(order.symbol)
            if last_price is None:
                raise InvalidOrderError("Market orders require fill_price or a known market price for reservation.")
            return last_price
        if order.order_type is OrderType.LIMIT:
            return self._required_decimal(order.limit_price, field_name="limit_price")
        if order.order_type is OrderType.STOP:
            return self._required_decimal(order.stop_price, field_name="stop_price")
        if order.order_type is OrderType.STOP_LIMIT:
            return self._required_decimal(order.limit_price, field_name="limit_price")
        raise InvalidOrderError(f"Unsupported order type: {order.order_type.value}")

    def _required_decimal(self, value: Decimal | None, *, field_name: str) -> Decimal:
        if value is None:
            raise InvalidOrderError(f"Missing required decimal field: {field_name}")
        return value

    def _calculate_fee(self, quantity: Decimal, price: Decimal) -> Decimal:
        return quantize_decimal(quantity * price * self.fee_rate)

    def _should_fill_order(self, order: OrderSnapshot, market_price: Decimal) -> bool:
        if order.order_type is OrderType.LIMIT:
            if order.side is OrderSide.BUY:
                return market_price <= self._required_decimal(order.limit_price, field_name="limit_price")
            return market_price >= self._required_decimal(order.limit_price, field_name="limit_price")

        if order.order_type is OrderType.STOP:
            if order.side is OrderSide.BUY:
                return market_price >= self._required_decimal(order.stop_price, field_name="stop_price")
            return market_price <= self._required_decimal(order.stop_price, field_name="stop_price")

        if order.order_type is OrderType.STOP_LIMIT:
            stop_price = self._required_decimal(order.stop_price, field_name="stop_price")
            limit_price = self._required_decimal(order.limit_price, field_name="limit_price")
            if order.side is OrderSide.BUY:
                return market_price >= stop_price and market_price <= limit_price
            return market_price <= stop_price and market_price >= limit_price

        return False

    def _resolve_fill_reason(self, order: OrderSnapshot) -> FillReason:
        if order.order_type is OrderType.LIMIT:
            return FillReason.LIMIT
        if order.order_type is OrderType.STOP:
            return FillReason.STOP
        if order.order_type is OrderType.STOP_LIMIT:
            return FillReason.STOP_LIMIT
        return FillReason.MARKET

    def _fill_order(
        self,
        order: OrderSnapshot,
        *,
        execution_price: Decimal,
        reason: FillReason,
        filled_at: datetime,
    ) -> FillSnapshot:
        execution_price = quantize_decimal(execution_price)
        fee = self._calculate_fee(order.quantity, execution_price)

        if order.side is OrderSide.BUY:
            self._apply_buy_fill(order, execution_price=execution_price, fee=fee, filled_at=filled_at)
        else:
            self._apply_sell_fill(order, execution_price=execution_price, fee=fee, filled_at=filled_at)

        fill = FillSnapshot(
            id=build_fill_id(self.asset_class),
            order_id=order.id,
            symbol=order.symbol,
            asset_class=self.asset_class,
            side=order.side,
            quantity=order.quantity,
            price=execution_price,
            fee=fee,
            reason=reason,
            filled_at=filled_at,
        )
        self._fills.append(fill)

        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.average_fill_price = execution_price
        order.fee_paid = fee
        order.updated_at = filled_at

        self._last_prices[order.symbol] = execution_price
        if order.symbol in self._positions:
            self._mark_position(order.symbol, execution_price, filled_at)

        return fill

    def _apply_buy_fill(
        self,
        order: OrderSnapshot,
        *,
        execution_price: Decimal,
        fee: Decimal,
        filled_at: datetime,
    ) -> None:
        cash_delta = quantize_decimal((order.quantity * execution_price) + fee)
        self._balance.total = quantize_decimal(self._balance.total - cash_delta)
        self._balance.reserved = quantize_decimal(self._balance.reserved - order.reserved_cash)
        refund = quantize_decimal(order.reserved_cash - cash_delta)
        self._balance.available = quantize_decimal(self._balance.available + refund)
        self._balance.updated_at = filled_at
        order.reserved_cash = ZERO

        position = self._positions.get(order.symbol)
        if position is None:
            total_cost = cash_delta
            new_quantity = order.quantity
            average_entry_price = quantize_decimal(total_cost / new_quantity)
            self._positions[order.symbol] = PositionSnapshot(
                symbol=order.symbol,
                asset_class=self.asset_class,
                quantity=new_quantity,
                reserved_quantity=ZERO,
                average_entry_price=average_entry_price,
                market_price=execution_price,
                market_value=quantize_decimal(new_quantity * execution_price),
                unrealized_pnl=quantize_decimal((execution_price - average_entry_price) * new_quantity),
                updated_at=filled_at,
            )
            return

        current_cost_basis = quantize_decimal(position.quantity * position.average_entry_price)
        additional_cost_basis = cash_delta
        new_quantity = quantize_decimal(position.quantity + order.quantity)
        average_entry_price = quantize_decimal((current_cost_basis + additional_cost_basis) / new_quantity)
        position.quantity = new_quantity
        position.average_entry_price = average_entry_price
        position.updated_at = filled_at

    def _apply_sell_fill(
        self,
        order: OrderSnapshot,
        *,
        execution_price: Decimal,
        fee: Decimal,
        filled_at: datetime,
    ) -> None:
        position = self._positions.get(order.symbol)
        if position is None or position.quantity < order.quantity:
            raise InsufficientPositionError(f"Cannot fill sell order for {order.symbol}; position is unavailable.")

        position.reserved_quantity = quantize_decimal(position.reserved_quantity - order.reserved_quantity)
        proceeds = quantize_decimal((order.quantity * execution_price) - fee)
        self._balance.total = quantize_decimal(self._balance.total + proceeds)
        self._balance.available = quantize_decimal(self._balance.available + proceeds)
        self._balance.updated_at = filled_at
        order.reserved_quantity = ZERO

        realized = quantize_decimal(((execution_price - position.average_entry_price) * order.quantity) - fee)
        self._realized_pnl = quantize_decimal(self._realized_pnl + realized)

        remaining_quantity = quantize_decimal(position.quantity - order.quantity)
        if remaining_quantity == ZERO:
            del self._positions[order.symbol]
            return

        position.quantity = remaining_quantity
        position.updated_at = filled_at

    def _mark_position(self, symbol: str, market_price: Decimal, updated_at: datetime) -> None:
        position = self._positions[symbol]
        position.market_price = quantize_decimal(market_price)
        position.market_value = quantize_decimal(position.quantity * position.market_price)
        position.unrealized_pnl = quantize_decimal((position.market_price - position.average_entry_price) * position.quantity)
        position.updated_at = updated_at
