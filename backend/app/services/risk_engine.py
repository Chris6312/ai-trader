from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.trading import Signal, SignalStatus
from app.risk import DeterministicRiskApprovalService, RiskApprovalInput, RiskApprovalResult
from app.services.risk_event_service import RiskEventService


class RiskEngineService:
    def __init__(self, approval_service: DeterministicRiskApprovalService | None = None) -> None:
        self._approval_service = approval_service or DeterministicRiskApprovalService()

    def evaluate_signal(
        self,
        db: Session,
        signal: Signal,
        approval_input: RiskApprovalInput,
        *,
        account_id: int | None = None,
    ) -> RiskApprovalResult:
        approval_result = self._approval_service.approve(approval_input)

        if account_id is not None:
            signal.account_id = account_id

        signal.status = SignalStatus.APPROVED if approval_result.approved else SignalStatus.REJECTED
        signal.reasoning = json.dumps(
            self._build_reasoning_payload(signal.reasoning, approval_result),
            default=str,
            sort_keys=True,
        )

        db.add(signal)
        db.commit()
        db.refresh(signal)

        if not approval_result.approved:
            RiskEventService.log_risk_rejection(
                db,
                approval_input,
                approval_result,
                account_id=signal.account_id,
                signal_id=signal.id,
            )

        return approval_result

    def _build_reasoning_payload(
        self,
        existing_reasoning: str | None,
        approval_result: RiskApprovalResult,
    ) -> dict[str, Any]:
        strategy_reasoning = self._load_existing_reasoning(existing_reasoning)
        return {
            "strategy_reasoning": strategy_reasoning,
            "risk_approval": {
                "approved": approval_result.approved,
                "rejection_reason": approval_result.rejection_reason.value if approval_result.rejection_reason else None,
                "summary": approval_result.reasoning.summary,
                "checks": approval_result.reasoning.checks,
                "inputs": approval_result.reasoning.inputs,
                "computed": approval_result.reasoning.computed,
                "rejection_path": approval_result.reasoning.rejection_path,
            },
        }

    def _load_existing_reasoning(self, existing_reasoning: str | None) -> dict[str, Any]:
        if not existing_reasoning:
            return {}
        try:
            loaded = json.loads(existing_reasoning)
        except json.JSONDecodeError:
            return {"raw_reasoning": existing_reasoning}
        return loaded if isinstance(loaded, dict) else {"raw_reasoning": loaded}
