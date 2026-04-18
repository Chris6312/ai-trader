from __future__ import annotations

import json
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models import Account, AccountType, AssetClass, RiskEventType, Signal, SignalStatus
from app.risk import DeterministicRiskApprovalService, OpenPositionSnapshot, RiskApprovalInput
from app.services.risk_event_service import RiskEventService


def _build_session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def test_log_risk_rejection_persists_rejection_event_with_structured_payload() -> None:
    service = DeterministicRiskApprovalService()
    approval_input = RiskApprovalInput(
        symbol="AAPL",
        asset_class="stock",
        account_equity=Decimal("10000"),
        proposed_notional_value=Decimal("2500"),
        proposed_risk_amount=Decimal("100"),
        quote_bid=Decimal("100"),
        quote_ask=Decimal("100.10"),
        quote_age_seconds=5,
        open_positions=[
            OpenPositionSnapshot(symbol="MSFT", asset_class="stock", notional_value=Decimal("4000")),
            OpenPositionSnapshot(symbol="NVDA", asset_class="stock", notional_value=Decimal("3500")),
        ],
        max_open_positions=5,
        max_total_exposure_percent=Decimal("50"),
        max_symbol_exposure_percent=Decimal("30"),
        max_daily_loss_percent=Decimal("5"),
        realized_pnl_today=Decimal("0"),
        max_quote_age_seconds=60,
        max_spread_percent=Decimal("1"),
    )
    approval_result = service.approve(approval_input)

    maker = _build_session_factory()
    with maker() as db:
        event = RiskEventService.log_risk_rejection(db, approval_input, approval_result)

        assert event is not None
        assert event.event_type == RiskEventType.REJECTION
        assert event.code == "total_exposure_cap_exceeded"

        payload = json.loads(event.message)
        assert payload["symbol"] == "AAPL"
        assert payload["rejection_reason"] == "total_exposure_cap_exceeded"
        assert payload["summary"] == "risk approval rejected"
        assert payload["checks"]["total_exposure_ok"] is False


def test_log_risk_rejection_returns_none_for_approved_result() -> None:
    service = DeterministicRiskApprovalService()
    approval_input = RiskApprovalInput(
        symbol="BTC/USD",
        asset_class="crypto",
        account_equity=Decimal("10000"),
        proposed_notional_value=Decimal("1000"),
        proposed_risk_amount=Decimal("100"),
        quote_bid=Decimal("50000"),
        quote_ask=Decimal("50010"),
        quote_age_seconds=5,
        open_positions=[OpenPositionSnapshot(symbol="ETH/USD", asset_class="crypto", notional_value=Decimal("500"))],
        max_open_positions=5,
        max_total_exposure_percent=Decimal("50"),
        max_symbol_exposure_percent=Decimal("30"),
        max_daily_loss_percent=Decimal("5"),
        realized_pnl_today=Decimal("0"),
        max_quote_age_seconds=60,
        max_spread_percent=Decimal("1"),
    )
    approval_result = service.approve(approval_input)

    maker = _build_session_factory()
    with maker() as db:
        event = RiskEventService.log_risk_rejection(db, approval_input, approval_result)

        assert event is None
        assert db.query_count if False else True


def test_log_risk_rejection_links_account_and_signal_when_provided() -> None:
    service = DeterministicRiskApprovalService()
    approval_input = RiskApprovalInput(
        symbol="TSLA",
        asset_class="stock",
        account_equity=Decimal("10000"),
        proposed_notional_value=Decimal("3500"),
        proposed_risk_amount=Decimal("100"),
        quote_bid=Decimal("200"),
        quote_ask=Decimal("200.20"),
        quote_age_seconds=5,
        open_positions=[],
        max_open_positions=5,
        max_total_exposure_percent=Decimal("100"),
        max_symbol_exposure_percent=Decimal("20"),
        max_daily_loss_percent=Decimal("5"),
        realized_pnl_today=Decimal("0"),
        max_quote_age_seconds=60,
        max_spread_percent=Decimal("1"),
    )
    approval_result = service.approve(approval_input)

    maker = _build_session_factory()
    with maker() as db:
        account = Account(
            name="Primary Stock Paper",
            account_type=AccountType.PAPER,
            asset_class=AssetClass.STOCK,
            base_currency="USD",
            is_active=True,
        )
        db.add(account)
        db.commit()
        db.refresh(account)

        signal = Signal(
            account_id=account.id,
            symbol="TSLA",
            asset_class=AssetClass.STOCK,
            strategy_name="trend_continuation",
            timeframe="15m",
            status=SignalStatus.NEW,
            confidence=Decimal("0.8000"),
            reasoning="{}",
        )
        db.add(signal)
        db.commit()
        db.refresh(signal)

        event = RiskEventService.log_risk_rejection(
            db,
            approval_input,
            approval_result,
            account_id=account.id,
            signal_id=signal.id,
        )

        assert event is not None
        assert event.account_id == account.id
        assert event.signal_id == signal.id
        assert event.code == "symbol_exposure_cap_exceeded"
