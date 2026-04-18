from __future__ import annotations

import json
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.trading import RiskEvent, RiskEventType, Signal, SignalStatus

router = APIRouter(prefix="/api/risk", tags=["risk"])


@router.get("/rejections/recent")
def get_recent_risk_rejections(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    events = (
        db.query(RiskEvent)
        .filter(RiskEvent.event_type == RiskEventType.REJECTION)
        .order_by(RiskEvent.created_at.desc(), RiskEvent.id.desc())
        .limit(50)
        .all()
    )

    payload: list[dict[str, object]] = []
    for event in events:
        parsed_message: dict[str, object] | None
        try:
            parsed_message = json.loads(event.message) if event.message else None
        except json.JSONDecodeError:
            parsed_message = {"raw_message": event.message}

        payload.append(
            {
                "id": event.id,
                "account_id": event.account_id,
                "signal_id": event.signal_id,
                "event_type": event.event_type.value if event.event_type is not None else None,
                "code": event.code,
                "message": event.message,
                "payload": parsed_message,
                "created_at": event.created_at.isoformat() if event.created_at is not None else None,
            }
        )

    return payload


@router.get("/signals/status-summary")
def get_signal_status_summary(db: Session = Depends(get_db)) -> dict[str, object]:
    counts = {
        status.value: 0 for status in SignalStatus
    }

    rows = (
        db.query(Signal.status, func.count(Signal.id))
        .group_by(Signal.status)
        .all()
    )

    for status, count in rows:
        key = status.value if hasattr(status, "value") else str(status)
        counts[key] = count

    total = sum(counts.values())
    approved = counts.get(SignalStatus.APPROVED.value, 0)
    rejected = counts.get(SignalStatus.REJECTED.value, 0)

    if total > 0:
        approval_rate_percent = float(
            (Decimal(approved) * Decimal("100") / Decimal(total)).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )
        )
        rejection_rate_percent = float(
            (Decimal(rejected) * Decimal("100") / Decimal(total)).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )
        )
    else:
        approval_rate_percent = 0.0
        rejection_rate_percent = 0.0

    return {
        "total": total,
        "new": counts.get(SignalStatus.NEW.value, 0),
        "approved": approved,
        "rejected": rejected,
        "executed": counts.get(SignalStatus.EXECUTED.value, 0),
        "approval_rate_percent": approval_rate_percent,
        "rejection_rate_percent": rejection_rate_percent,
    }