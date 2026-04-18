from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.risk import RiskApprovalInput, RiskApprovalResult
from app.services.execution_engine import PaperExecutionEngine, PaperExecutionRequest
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
    executed: bool = False
    execution_order_id: int | None = None
    execution_error: str | None = None


engine = StrategyEngine()
risk_engine = RiskEngineService()
execution_engine = PaperExecutionEngine()


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


def evaluate_from_candles_with_risk_and_execution(
    db: Session,
    bundle: StrategyInputBundle,
    approval_inputs_by_strategy: dict[str, RiskApprovalInput],
    execution_requests_by_strategy: dict[str, PaperExecutionRequest],
    *,
    account_id: int | None = None,
) -> list[StrategyRuntimeRiskRecord]:
    runtime_records = evaluate_from_candles_with_risk(
        db=db,
        bundle=bundle,
        approval_inputs_by_strategy=approval_inputs_by_strategy,
        account_id=account_id,
    )

    for record in runtime_records:
        if record.signal_id is None or record.approved is not True:
            continue

        execution_request = execution_requests_by_strategy.get(record.strategy)
        if execution_request is None:
            record.execution_error = "missing_execution_request"
            continue

        execution_request.signal_id = record.signal_id
        try:
            execution_result = execution_engine.execute_approved_signal(db=db, request=execution_request)
        except Exception as exc:  # pragma: no cover - surfaced in runtime record for deterministic inspection
            record.execution_error = str(exc)
            continue

        record.executed = execution_result.executed
        record.execution_order_id = execution_result.db_order_id

    return runtime_records
