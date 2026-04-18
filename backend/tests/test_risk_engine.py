from __future__ import annotations

import json
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.trading import AssetClass, RiskEvent, RiskEventType, Signal, SignalStatus
from app.risk.types import OpenPositionSnapshot, RiskApprovalInput
from app.services.risk_engine import RiskEngineService


def _build_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def test_risk_engine_service_marks_signal_approved_and_embeds_risk_reasoning() -> None:
    service = RiskEngineService()

    with _build_session() as db:
        signal = Signal(
            symbol="AAPL",
            asset_class=AssetClass.STOCK,
            strategy_name="momentum",
            timeframe="15m",
            confidence=Decimal("0.8500"),
            reasoning=json.dumps({"strategy": {"summary": "momentum confirmed"}}),
            status=SignalStatus.NEW,
        )
        db.add(signal)
        db.commit()
        db.refresh(signal)

        result = service.evaluate_signal(
            db,
            signal,
            RiskApprovalInput(
                symbol="AAPL",
                asset_class="stock",
                account_equity=Decimal("10000"),
                proposed_notional_value=Decimal("1500"),
                proposed_risk_amount=Decimal("100"),
                quote_bid=Decimal("99.95"),
                quote_ask=Decimal("100.05"),
                quote_age_seconds=5,
                open_positions=[],
                max_open_positions=5,
                max_total_exposure_percent=Decimal("50"),
                max_symbol_exposure_percent=Decimal("30"),
                max_daily_loss_percent=Decimal("3"),
                max_quote_age_seconds=30,
                max_spread_percent=Decimal("0.50"),
            ),
        )

        db.refresh(signal)
        payload = json.loads(signal.reasoning or "{}")
        risk_events = db.scalars(select(RiskEvent)).all()

        assert result.approved is True
        assert signal.status == SignalStatus.APPROVED
        assert payload["strategy_reasoning"]["strategy"]["summary"] == "momentum confirmed"
        assert payload["risk_approval"]["approved"] is True
        assert payload["risk_approval"]["rejection_reason"] is None
        assert risk_events == []



def test_risk_engine_service_marks_signal_rejected_and_logs_risk_event() -> None:
    service = RiskEngineService()

    with _build_session() as db:
        signal = Signal(
            account_id=7,
            symbol="NVDA",
            asset_class=AssetClass.STOCK,
            strategy_name="trend_continuation",
            timeframe="1h",
            confidence=Decimal("0.9100"),
            reasoning=json.dumps({"strategy": {"summary": "trend aligned"}}),
            status=SignalStatus.NEW,
        )
        db.add(signal)
        db.commit()
        db.refresh(signal)

        result = service.evaluate_signal(
            db,
            signal,
            RiskApprovalInput(
                symbol="NVDA",
                asset_class="stock",
                account_equity=Decimal("10000"),
                proposed_notional_value=Decimal("2200"),
                proposed_risk_amount=Decimal("100"),
                quote_bid=Decimal("899.50"),
                quote_ask=Decimal("900.50"),
                quote_age_seconds=5,
                open_positions=[
                    OpenPositionSnapshot(symbol="AAPL", asset_class="stock", notional_value=Decimal("1800")),
                    OpenPositionSnapshot(symbol="MSFT", asset_class="stock", notional_value=Decimal("1500")),
                ],
                max_open_positions=5,
                max_total_exposure_percent=Decimal("50"),
                max_symbol_exposure_percent=Decimal("30"),
                max_daily_loss_percent=Decimal("3"),
                max_quote_age_seconds=30,
                max_spread_percent=Decimal("0.50"),
            ),
        )

        db.refresh(signal)
        payload = json.loads(signal.reasoning or "{}")
        risk_events = db.scalars(select(RiskEvent)).all()

        assert result.approved is False
        assert signal.status == SignalStatus.REJECTED
        assert payload["risk_approval"]["approved"] is False
        assert payload["risk_approval"]["rejection_reason"] == "total_exposure_cap_exceeded"
        assert len(risk_events) == 1
        assert risk_events[0].event_type == RiskEventType.REJECTION
        assert risk_events[0].signal_id == signal.id
        assert risk_events[0].account_id == 7
        event_payload = json.loads(risk_events[0].message)
        assert event_payload["summary"] == "risk approval rejected"
        assert event_payload["rejection_reason"] == "total_exposure_cap_exceeded"
