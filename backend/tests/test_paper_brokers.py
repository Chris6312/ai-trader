from __future__ import annotations

from decimal import Decimal

import pytest

from app.brokers import CryptoPaperBroker, InsufficientFundsError, OrderRequest, StockPaperBroker
from app.models import OrderSide, OrderStatus, OrderType



def test_stock_market_buy_updates_cash_and_position() -> None:
    broker = StockPaperBroker(initial_cash=Decimal("1000"))

    order = broker.place_order(
        OrderRequest(
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("5"),
        ),
        fill_price=Decimal("100"),
    )

    assert order.status is OrderStatus.FILLED

    balance = broker.get_balance()
    assert balance.total == Decimal("500.00000000")
    assert balance.available == Decimal("500.00000000")
    assert balance.reserved == Decimal("0.00000000")

    positions = broker.list_positions()
    assert len(positions) == 1
    assert positions[0].symbol == "AAPL"
    assert positions[0].quantity == Decimal("5.00000000")
    assert positions[0].average_entry_price == Decimal("100.00000000")

    broker.process_price_update("AAPL", Decimal("110"))
    account = broker.get_account_snapshot()
    assert account.unrealized_pnl == Decimal("50.00000000")
    assert account.equity == Decimal("1050.00000000")



def test_limit_buy_reserves_cash_then_fills_on_price_cross() -> None:
    broker = StockPaperBroker(initial_cash=Decimal("1000"))

    order = broker.place_order(
        OrderRequest(
            symbol="MSFT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("2"),
            limit_price=Decimal("200"),
        )
    )

    assert order.status is OrderStatus.OPEN
    balance = broker.get_balance()
    assert balance.available == Decimal("600.00000000")
    assert balance.reserved == Decimal("400.00000000")

    fills = broker.process_price_update("MSFT", Decimal("210"))
    assert fills == []
    assert broker.list_orders(status=OrderStatus.OPEN)[0].id == order.id

    fills = broker.process_price_update("MSFT", Decimal("199"))
    assert len(fills) == 1
    assert fills[0].price == Decimal("199.00000000")

    balance = broker.get_balance()
    assert balance.total == Decimal("602.00000000")
    assert balance.available == Decimal("602.00000000")
    assert balance.reserved == Decimal("0.00000000")



def test_cancel_open_sell_releases_reserved_position_quantity() -> None:
    broker = StockPaperBroker(initial_cash=Decimal("1000"))
    broker.place_order(
        OrderRequest(
            symbol="NVDA",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("10"),
        ),
        fill_price=Decimal("10"),
    )

    sell_order = broker.place_order(
        OrderRequest(
            symbol="NVDA",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=Decimal("4"),
            limit_price=Decimal("15"),
        )
    )

    position = broker.list_positions()[0]
    assert position.reserved_quantity == Decimal("4.00000000")

    canceled = broker.cancel_order(sell_order.id)
    assert canceled.status is OrderStatus.CANCELED

    position = broker.list_positions()[0]
    assert position.reserved_quantity == Decimal("0.00000000")



def test_crypto_round_trip_tracks_fees_and_realized_pnl() -> None:
    broker = CryptoPaperBroker(initial_cash=Decimal("20000"))

    broker.place_order(
        OrderRequest(
            symbol="BTCUSD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.5"),
        ),
        fill_price=Decimal("20000"),
    )

    balance = broker.get_balance()
    assert balance.total == Decimal("9975.00000000")

    broker.place_order(
        OrderRequest(
            symbol="BTCUSD",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.25"),
        ),
        fill_price=Decimal("21000"),
    )

    account = broker.get_account_snapshot()
    assert account.realized_pnl == Decimal("224.37500000")
    assert account.cash_total == Decimal("15211.87500000")

    positions = broker.list_positions()
    assert len(positions) == 1
    assert positions[0].quantity == Decimal("0.25000000")



def test_buy_order_rejects_when_cash_is_too_low() -> None:
    broker = StockPaperBroker(initial_cash=Decimal("50"))

    with pytest.raises(InsufficientFundsError):
        broker.place_order(
            OrderRequest(
                symbol="SPY",
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=Decimal("1"),
                limit_price=Decimal("100"),
            )
        )
