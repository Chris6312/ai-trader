from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.trading import RiskEvent, RiskEventType
from app.risk.types import RiskApprovalInput, RiskApprovalResult


class RiskEventService:
    @staticmethod
    def log_risk_rejection(
        db: Session,
        approval_input: RiskApprovalInput,
        approval_result: RiskApprovalResult,
        *,
        account_id: int | None = None,
        signal_id: int | None = None,
    ) -> RiskEvent | None:
        if approval_result.approved or approval_result.rejection_reason is None:
            return None

        payload = RiskEventService._build_rejection_payload(
            approval_input=approval_input,
            approval_result=approval_result,
        )

        event = RiskEvent(
            account_id=account_id,
            signal_id=signal_id,
            event_type=RiskEventType.REJECTION,
            code=approval_result.rejection_reason.value,
            message=json.dumps(payload, sort_keys=True),
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    @staticmethod
    def _build_rejection_payload(
        *,
        approval_input: RiskApprovalInput,
        approval_result: RiskApprovalResult,
    ) -> dict[str, Any]:
        return {
            "summary": "risk approval rejected",
            "symbol": approval_input.symbol,
            "asset_class": approval_input.asset_class,
            "rejection_reason": approval_result.rejection_reason.value
            if approval_result.rejection_reason is not None
            else None,
            "reasoning_summary": approval_result.reasoning.summary,
            "checks": approval_result.reasoning.checks,
            "inputs": approval_result.reasoning.inputs,
            "computed": approval_result.reasoning.computed,
            "rejection_path": approval_result.reasoning.rejection_path,
        }