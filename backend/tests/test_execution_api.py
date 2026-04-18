from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.trading import Account, AccountType, AssetClass, Signal, SignalStatus
from app.services.execution_engine import PaperExecutionEngine, PaperExecutionRequest


def _build_test_sessionmaker():
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    return TestingSessionLocal


def _create_executed_signal(db):
    account = Account(
        name="stock-paper",
        account_type=AccountType.PAPER,
        asset_class=AssetClass.STOCK,
        base_currency="USD",
        is_active=True,
    )
    db.add(account)
    db.flush()

    signal = Signal(
        account_id=account.id,
        symbol="AAPL",
        asset_class=AssetClass.STOCK,
        strategy_name="momentum",
        timeframe="1h",
        status=SignalStatus.APPROVED,
        confidence=0.9,
        reasoning="{}",
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)

    engine = PaperExecutionEngine()
    engine.execute_approved_signal(
        db,
        PaperExecutionRequest(signal_id=signal.id, quantity=Decimal("3"), fill_price=Decimal("150.50")),
    )
    db.refresh(signal)
    return signal


def test_recent_execution_endpoint_returns_execution_payload():
    testing_session_factory = _build_test_sessionmaker()

    with testing_session_factory() as db:
        signal = _create_executed_signal(db)
        signal_id = signal.id

    def override_get_db():
        db = testing_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    response = client.get("/api/execution/recent")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["signal_id"] == signal_id
    assert payload[0]["symbol"] == "AAPL"
    assert payload[0]["quantity"] == "3"
    assert payload[0]["fill_price"] == "150.50"
    assert payload[0]["execution_summary"] == "paper execution completed"
    assert payload[0]["broker_order_id"] is not None
    assert payload[0]["db_order_id"] is not None
    assert payload[0]["db_fill_id"] is not None
    assert payload[0]["executed_at"] is not None


def test_execution_summary_endpoint_counts_execution_states():
    testing_session_factory = _build_test_sessionmaker()

    with testing_session_factory() as db:
        _create_executed_signal(db)
        db.add(
            Signal(
                symbol="MSFT",
                asset_class=AssetClass.STOCK,
                strategy_name="trend_continuation",
                timeframe="1h",
                confidence=0.77,
                reasoning="{}",
                status=SignalStatus.NEW,
            )
        )
        db.commit()

    def override_get_db():
        db = testing_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    response = client.get("/api/execution/summary")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["new"] == 1
    assert payload["approved"] == 0
    assert payload["rejected"] == 0
    assert payload["executed"] == 1
    assert payload["recent_execution_count"] == 1


def test_recent_execution_endpoint_supports_asset_class_and_symbol_filters():
    testing_session_factory = _build_test_sessionmaker()

    with testing_session_factory() as db:
        _create_executed_signal(db)
        crypto_account = Account(
            name="crypto-paper",
            account_type=AccountType.PAPER,
            asset_class=AssetClass.CRYPTO,
            base_currency="USD",
            is_active=True,
        )
        db.add(crypto_account)
        db.flush()

        crypto_signal = Signal(
            account_id=crypto_account.id,
            symbol="BTCUSD",
            asset_class=AssetClass.CRYPTO,
            strategy_name="momentum",
            timeframe="1h",
            status=SignalStatus.APPROVED,
            confidence=0.91,
            reasoning="{}",
        )
        db.add(crypto_signal)
        db.commit()
        db.refresh(crypto_signal)

        PaperExecutionEngine().execute_approved_signal(
            db,
            PaperExecutionRequest(
                signal_id=crypto_signal.id,
                quantity=Decimal("0.25"),
                fill_price=Decimal("65000.125"),
            ),
        )

    def override_get_db():
        db = testing_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    response = client.get("/api/execution/recent", params={"asset_class": "crypto", "symbol": "btcusd"})

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["asset_class"] == "crypto"
    assert payload[0]["symbol"] == "BTCUSD"
    assert payload[0]["fill_price"] == "65000.125"


def test_execution_summary_endpoint_supports_account_filter():
    testing_session_factory = _build_test_sessionmaker()

    with testing_session_factory() as db:
        stock_signal = _create_executed_signal(db)
        stock_account_id = stock_signal.account_id

        crypto_account = Account(
            name="crypto-paper",
            account_type=AccountType.PAPER,
            asset_class=AssetClass.CRYPTO,
            base_currency="USD",
            is_active=True,
        )
        db.add(crypto_account)
        db.flush()

        crypto_signal = Signal(
            account_id=crypto_account.id,
            symbol="ETHUSD",
            asset_class=AssetClass.CRYPTO,
            strategy_name="trend_continuation",
            timeframe="4h",
            status=SignalStatus.APPROVED,
            confidence=0.82,
            reasoning="{}",
        )
        db.add(crypto_signal)
        db.commit()
        db.refresh(crypto_signal)

        PaperExecutionEngine().execute_approved_signal(
            db,
            PaperExecutionRequest(
                signal_id=crypto_signal.id,
                quantity=Decimal("1.5"),
                fill_price=Decimal("3200.25"),
            ),
        )

    def override_get_db():
        db = testing_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    response = client.get("/api/execution/summary", params={"account_id": stock_account_id})

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["executed"] == 1
    assert payload["recent_execution_count"] == 1
    assert payload["approved"] == 0
    assert payload["rejected"] == 0
    assert payload["new"] == 0

def test_recent_execution_endpoint_preserves_primary_execution_truth_after_duplicate_attempt():
    testing_session_factory = _build_test_sessionmaker()

    with testing_session_factory() as db:
        signal = _create_executed_signal(db)
        PaperExecutionEngine().execute_approved_signal(
            db,
            PaperExecutionRequest(
                signal_id=signal.id,
                quantity=Decimal("3"),
                fill_price=Decimal("150.50"),
            ),
        )

    def override_get_db():
        db = testing_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    response = client.get("/api/execution/recent")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["symbol"] == "AAPL"
    assert payload[0]["execution_summary"] == "paper execution completed"
    assert payload[0]["skipped"] is False
    assert payload[0]["skip_reason"] is None


def test_execution_summary_endpoint_does_not_count_duplicate_attempts_as_recent_skips():
    testing_session_factory = _build_test_sessionmaker()

    with testing_session_factory() as db:
        signal = _create_executed_signal(db)
        PaperExecutionEngine().execute_approved_signal(
            db,
            PaperExecutionRequest(
                signal_id=signal.id,
                quantity=Decimal("3"),
                fill_price=Decimal("150.50"),
            ),
        )

    def override_get_db():
        db = testing_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    response = client.get("/api/execution/summary")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["executed"] == 1
    assert payload["recent_execution_count"] == 1
    assert payload["recent_skipped_count"] == 0
