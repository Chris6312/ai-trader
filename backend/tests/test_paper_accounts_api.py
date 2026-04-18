from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.brokers import OrderRequest
from app.main import app
from app.models import AssetClass, OrderSide, OrderStatus, OrderType
from app.services.paper_accounts import PaperAccountService


client = TestClient(app)


def _fresh_service() -> PaperAccountService:
    service = PaperAccountService(
        stock_initial_cash=Decimal("1000.00000000"),
        crypto_initial_cash=Decimal("500"),
    )
    app.state.paper_account_service = service
    return service


def test_summary_endpoint_returns_default_stock_account_state() -> None:
    _fresh_service()

    response = client.get("/api/paper/stock/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["asset_class"] == AssetClass.STOCK.value
    assert payload["cash_total"] == "1000.00000000"
    assert payload["position_count"] == 0
    assert payload["open_order_count"] == 0



def test_reset_balance_endpoint_rebuilds_account_state() -> None:
    _fresh_service()

    response = client.post("/api/paper/stock/reset-balance", json={"amount": "2500.00000000"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["cash_total"] == "2500.00000000"
    assert payload["cash_available"] == "2500.00000000"
    assert payload["cash_reserved"] == "0"



def test_cancel_order_and_cancel_all_release_open_orders() -> None:
    service = _fresh_service()
    stock_broker = service.get_broker(AssetClass.STOCK)
    first_order = stock_broker.place_order(
        OrderRequest(
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("2"),
            limit_price=Decimal("50"),
        )
    )
    stock_broker.place_order(
        OrderRequest(
            symbol="MSFT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("1"),
            limit_price=Decimal("100"),
        )
    )

    cancel_response = client.post(f"/api/paper/stock/orders/{first_order.id}/cancel")
    cancel_all_response = client.post("/api/paper/stock/orders/cancel-all")
    list_response = client.get("/api/paper/stock/orders?status_value=canceled")

    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == OrderStatus.CANCELED.value
    assert cancel_all_response.status_code == 200
    assert len(cancel_all_response.json()) == 1
    assert list_response.status_code == 200
    assert len(list_response.json()) == 2



def test_close_positions_liquidates_open_position() -> None:
    service = _fresh_service()
    stock_broker = service.get_broker(AssetClass.STOCK)
    stock_broker.place_order(
        OrderRequest(
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("2"),
        ),
        fill_price=Decimal("100"),
    )

    close_response = client.post("/api/paper/stock/positions/close")
    positions_response = client.get("/api/paper/stock/positions")
    summary_response = client.get("/api/paper/stock/summary")

    assert close_response.status_code == 200
    assert len(close_response.json()) == 1
    assert close_response.json()[0]["status"] == OrderStatus.FILLED.value
    assert positions_response.status_code == 200
    assert positions_response.json() == []
    assert summary_response.status_code == 200
    assert summary_response.json()["position_count"] == 0



def test_wipe_account_restores_default_cash_and_clears_state() -> None:
    service = _fresh_service()
    stock_broker = service.get_broker(AssetClass.STOCK)
    stock_broker.place_order(
        OrderRequest(
            symbol="NVDA",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("1"),
        ),
        fill_price=Decimal("200"),
    )

    response = client.post("/api/paper/stock/wipe")

    assert response.status_code == 200
    payload = response.json()
    assert payload["cash_total"] == "1000.00000000"
    assert payload["position_count"] == 0
    assert payload["open_order_count"] == 0


def test_reset_balance_persists_across_service_recreation() -> None:
    from app.db.base import Base

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)

    first_service = PaperAccountService(
        stock_initial_cash=Decimal("1000.00000000"),
        crypto_initial_cash=Decimal("500"),
        db_session_factory=TestingSessionLocal,
    )
    first_service.reset_balance(AssetClass.STOCK, Decimal("2500.00000000"))

    second_service = PaperAccountService(
        stock_initial_cash=Decimal("1000.00000000"),
        crypto_initial_cash=Decimal("500"),
        db_session_factory=TestingSessionLocal,
    )
    snapshot = second_service.get_account_snapshot(AssetClass.STOCK)

    assert snapshot.cash_total == Decimal("2500.00000000")
    assert snapshot.cash_available == Decimal("2500.00000000")
    assert snapshot.cash_reserved == Decimal("0")

    Base.metadata.drop_all(engine)
    engine.dispose()
