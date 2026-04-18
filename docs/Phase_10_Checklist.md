# Phase 10 - Execution Engine Foundation

## Goal
Transform approved signals into deterministic, idempotent, inspectable paper executions with stable contracts that can later support live broker adapters.

This checklist is the canonical scope guard for Phase 10.
It exists to prevent adding nice-to-have work that belongs in later phases.

---

## Reviewed Files In Scope

Primary implementation files:
- `backend/app/services/execution_engine.py`
- `backend/app/api/routes/execution.py`
- `backend/app/services/strategy_runtime_integration.py`

Primary test files:
- `backend/tests/test_execution_engine.py`
- `backend/tests/test_execution_api.py`
- `backend/tests/test_execution_runtime_integration.py`

Supporting model file reviewed for contract shape:
- `backend/app/models/trading.py`

Reference docs:
- `docs/ENGINEERING_STANDARD.md`
- `docs/PHASE_CHECKLIST.md`
- `docs/Python_3_12_Standards.md`

---

## Drift Audit Outcome After 10C

### Was post-10C work necessary?
Yes.

### Necessary drift fixes already completed

#### 10D - Necessary
These were correction-level fixes, not optional expansion work.

Completed because the Phase 10 execution contract was not actually stable after 10C:
- missing required `Fill.side` during fill persistence
- assumed nonexistent `Signal.updated_at`
- reconciliation logic was not aligned with the actual broker/repo interfaces
- invalid quantity and invalid fill price did not have deterministic guard behavior
- execution metadata needed explicit JSON-safety validation

#### 10E - Necessary
This was also valid Phase 10 work, not scope drift.

Completed because operator inspection and audit contracts were incomplete:
- execution audit filters were added for `account_id`, `asset_class`, and `symbol`
- summary endpoint bug fixed where filters were accepted but not passed to service layer
- API tests hardened to avoid detached SQLAlchemy instance mistakes

### Audit conclusion
10D and 10E were legitimate completion work for Phase 10 because they fixed broken or incomplete behavior in the execution contract that already existed by 10C.
They should remain part of Phase 10 history and should not be treated as accidental scope creep.

---

## Phase 10 Status Board

| Slice | Title | Status | Notes |
| --- | --- | --- | --- |
| 10A | Paper execution engine foundation | Complete | Approved signals can execute through paper broker flow |
| 10B | Execution idempotency hardening | Complete | Duplicate execution attempts skip deterministically |
| 10C | Execution audit visibility | Complete | Recent and summary endpoints added |
| 10D | Execution validation guards | Complete | Contract and reconciliation bug-net slice |
| 10E | Execution audit filters | Complete | Operator filtering and route pass-through fixed |
| 10F | Execution result contract normalization | Open | Current result shape still too thin and inconsistent |
| 10G | Execution reason code registry | Open | Skip reasons still free-text strings |
| 10H | Execution persistence contract hardening | Open | Execution payload in `Signal.reasoning` still incomplete |
| 10I | Execution inspection consistency | Open | Recent execution endpoint still reconstructs some fields instead of reading stable persisted truth |
| 10J | Execution boundary separation | Complete | Current execution engine stays out of strategy/risk/candle evaluation |

---

## Remaining Finite Work

Only the items below remain in scope for Phase 10.
Anything outside this list should be treated as Phase 11+ unless it is a direct bug fix against these contracts.

### 10F - Execution Result Contract Normalization

#### Problem
`PaperExecutionResult` still returns a narrow boolean-style shape:
- `executed`
- `skipped`
- `skip_reason`
- `db_order_id`
- `db_fill_id`
- `order_status`

This forces callers to infer meaning instead of consuming one canonical result contract.

#### Required outcome
Create one canonical result envelope for all expected execution outcomes.

#### Minimum contract target
```python
ExecutionResult(
    outcome: Literal[
        "executed",
        "skipped",
        "duplicate",
        "invalid",
        "not_approved",
    ],
    signal_id: int,
    account_id: int | None,
    asset_class: AssetClass | None,
    symbol: str | None,
    quantity: Decimal | None,
    fill_price: Decimal | None,
    skip_reason: str | None,
    execution_summary: str,
    executed_at: datetime | None,
    db_order_id: int | None,
    db_fill_id: int | None,
    broker_order_id: str | None,
)
```

#### Acceptance criteria
- every execution attempt returns a structured result object
- no silent `None` result paths
- no exceptions for expected contract states
- duplicate, invalid, and not-approved outcomes are explicitly distinguishable

#### Primary files
- `backend/app/services/execution_engine.py`
- `backend/app/services/strategy_runtime_integration.py`
- `backend/tests/test_execution_engine.py`
- `backend/tests/test_execution_runtime_integration.py`

---

### 10G - Execution Reason Code Registry

#### Problem
Skip reasons are still ad hoc strings and can drift over time.
Some are single codes and some are semicolon-joined validation strings.

#### Required outcome
Introduce stable reason codes for deterministic operator and UI handling.

#### Minimum reason code set
```python
ExecutionSkipReason:
    SIGNAL_NOT_FOUND
    SIGNAL_NOT_APPROVED
    SIGNAL_ALREADY_EXECUTED
    INVALID_QUANTITY
    INVALID_FILL_PRICE
    INVALID_METADATA
    MISSING_TIMEFRAME
    ACCOUNT_NOT_FOUND
    EXECUTION_ERROR
```

#### Acceptance criteria
- all skip paths use controlled vocabulary
- validation errors do not return free-form joined strings
- summary text may remain human-readable, but reason codes must stay stable

#### Primary files
- `backend/app/services/execution_engine.py`
- `backend/tests/test_execution_engine.py`
- `backend/tests/test_execution_runtime_integration.py`

---

### 10H - Execution Persistence Contract Hardening

#### Problem
The current `reasoning["execution"]` block is useful but incomplete.
It does not yet persist the full stable execution contract needed for replay and inspection.

#### Current block
```json
{
  "summary": "paper execution completed",
  "timeframe": "1h",
  "quantity": "10",
  "fill_price": "100",
  "validation": {
    "valid": true,
    "errors": []
  },
  "metadata": {}
}
```

#### Required persisted contract
```json
{
  "status": "executed|skipped|duplicate|invalid|not_approved",
  "summary": "...",
  "timeframe": "1h",
  "quantity": "decimal-string-or-null",
  "fill_price": "decimal-string-or-null",
  "executed_at": "iso-timestamp-or-null",
  "broker_order_id": "string-or-null",
  "db_order_id": 1,
  "db_fill_id": 1,
  "skip_reason": "REASON_CODE_OR_NULL",
  "validation": {
    "valid": true,
    "errors": []
  },
  "metadata": {}
}
```

#### Acceptance criteria
- execution metadata remains JSON serializable
- decimals are serialized as strings
- datetimes are serialized explicitly, not as raw objects
- result survives restart, re-read, and future live-adapter expansion

#### Primary files
- `backend/app/services/execution_engine.py`
- `backend/tests/test_execution_engine.py`
- `backend/tests/test_execution_api.py`

---

### 10I - Execution Inspection Consistency

#### Problem
`/api/execution/recent` currently reconstructs several values from `Signal.reasoning` and synthetic assumptions.
Examples:
- `executed_at` is currently mapped from `Signal.created_at`
- `broker_order_id`, `db_order_id`, and `db_fill_id` are currently returned as `None`

This works as a temporary lane but is not full audit truth yet.

#### Required outcome
Make inspection endpoints reflect stable persisted execution truth.

#### Acceptance criteria
- recent execution rows match actual execution persistence state
- duplicate execution attempts do not produce phantom records
- skipped execution attempts do not appear as executed rows
- filtered recent and summary endpoints stay deterministic
- `executed_at` is no longer synthesized from `Signal.created_at`

#### Primary files
- `backend/app/services/execution_engine.py`
- `backend/app/api/routes/execution.py`
- `backend/tests/test_execution_engine.py`
- `backend/tests/test_execution_api.py`

---

## Explicitly Out of Scope for Phase 10

These are not Phase 10 tasks unless a bug directly blocks a remaining item above:
- AI ranking or model logic
- live broker adapters
- exit worker execution flow beyond direct reuse planning
- advanced pagination/sorting UX polish
- observability platform work beyond execution contract correctness
- holiday / early-close stock calendar modeling

---

## Phase 10 Exit Criteria

Phase 10 is complete when all conditions below are true:
1. execution always returns one canonical structured result object
2. skip reasons use stable controlled codes
3. execution persistence payload is stable and JSON-safe
4. execution inspection endpoints reflect real persisted execution truth
5. execution remains idempotent across repeated runtime passes
6. execution engine stays isolated from strategy, risk, and candle-fetching concerns

---

## Working Rule For Future Handoffs

Do not use generic repeating bullets like "richer visibility" or "stronger audit detail" in the Phase 10 handoff.
Only reference incomplete items from this checklist by slice number and title.

Allowed examples:
- `Phase 10F - Execution result contract normalization`
- `Phase 10H - Execution persistence contract hardening`

Not allowed:
- "continue hardening"
- "improve visibility"
- "possible refinements"
