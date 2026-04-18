from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.risk import RiskApprovalInput, RiskApprovalResult
from app.services.risk_engine import RiskEngineService
from app.services.strategy_engine import StrategyEngine
from app.strategies.types import StrategyInputBundle


@dataclass
class StrategyRuntimeRiskRecord:
    strategy: str
    signal_id: int | None
    passed_strategy: bool
    approved: bool | None
    rejection_reason: str | None


engine = StrategyEngine()
risk_engine = RiskEngineService()


def evaluate_from_candles(db: Session, bundle: StrategyInputBundle):
    return engine.evaluate_symbol(db=db, bundle=bundle)


def evaluate_from_candles_with_risk(
    db: Session,
    bundle: StrategyInputBundle,
    approval_inputs_by_strategy: dict[str, RiskApprovalInput],
    *,
    account_id: int | None = None,
) -> list[StrategyRuntimeRiskRecord]:
    evaluation_records = engine.evaluate_symbol_with_records(db=db, bundle=bundle)
    runtime_records: list[StrategyRuntimeRiskRecord] = []

    for record in evaluation_records:
        if not record.result.passed or record.signal is None:
            runtime_records.append(
                StrategyRuntimeRiskRecord(
                    strategy=record.result.strategy,
                    signal_id=None,
                    passed_strategy=False,
                    approved=None,
                    rejection_reason=None,
                )
            )
            continue

        approval_input = approval_inputs_by_strategy.get(record.result.strategy)
        if approval_input is None:
            runtime_records.append(
                StrategyRuntimeRiskRecord(
                    strategy=record.result.strategy,
                    signal_id=record.signal.id,
                    passed_strategy=True,
                    approved=None,
                    rejection_reason="missing_risk_approval_input",
                )
            )
            continue

        approval_result: RiskApprovalResult = risk_engine.evaluate_signal(
            db=db,
            signal=record.signal,
            approval_input=approval_input,
            account_id=account_id,
        )
        runtime_records.append(
            StrategyRuntimeRiskRecord(
                strategy=record.result.strategy,
                signal_id=record.signal.id,
                passed_strategy=True,
                approved=approval_result.approved,
                rejection_reason=approval_result.rejection_reason.value if approval_result.rejection_reason else None,
            )
        )

    return runtime_records
