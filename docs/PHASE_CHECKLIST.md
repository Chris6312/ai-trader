# PHASE_CHECKLIST.md

## Phase 1 - Foundation and Infrastructure
### Goal
Create the clean baseline project structure and verify the stack boots.

### Tasks
- Create project folders
- Create Python 3.12 virtual environment
- Install backend runtime dependencies
- Install ML dependencies
- Scaffold React + TypeScript frontend
- Add Tailwind and core frontend libraries
- Create Docker Compose for PostgreSQL and Redis
- Create `.env`
- Create backend config, DB base, DB session, and FastAPI app
- Verify `/health` endpoint works

### Deliverables
- PostgreSQL running in Docker
- Redis running in Docker
- FastAPI app running locally
- React app scaffolded
- Engineering standard document created
- Phase checklist document created

### Exit Criteria
- `docker compose ps` shows postgres and redis running
- backend starts successfully with Uvicorn
- `Invoke-RestMethod http://127.0.0.1:8000/health` returns ok

---

## Phase 2 - Database and Migration Foundation
### Goal
Set up SQLAlchemy models and Alembic migration flow.

### Tasks
- Initialize Alembic
- Wire metadata imports cleanly
- Create initial core tables:
  - accounts
  - balances
  - orders
  - fills
  - positions
  - signals
  - risk_events
- Run first migration
- Verify tables in PostgreSQL

### Deliverables
- Working Alembic setup
- Initial database schema in PostgreSQL

### Exit Criteria
- `alembic upgrade head` succeeds
- tables exist and are queryable

---

## Phase 3 - Paper Broker Core
### Goal
Implement internal paper broker support for both stocks and crypto.

### Tasks
- Define shared broker interface
- Implement stock paper broker
- Implement crypto paper broker
- Add balance tracking
- Add open order tracking
- Add position tracking
- Add fill logic
- Add fee handling
- Add realized and unrealized PnL

### Deliverables
- Functional paper broker domain layer
- Unit tests for order lifecycle and balances

### Exit Criteria
- Paper orders can be placed, filled, canceled, and reflected in balances and positions

---

## Phase 4 - Paper Account Controls API
### Goal
Expose backend controls that behave like a paper broker account console.

### Tasks
- Add endpoints for:
  - account summary
  - balances
  - positions
  - orders
  - reset balance
  - wipe account
  - cancel order
  - cancel all open orders
  - close positions
- Add audit logging for control actions

### Deliverables
- Paper account API for stock and crypto paper accounts

### Exit Criteria
- API can fully manage paper accounts without direct DB edits

---

## Phase 5 - Frontend App Shell
### Goal
Build the initial frontend structure and shared layout.

### Tasks
- Add app shell
- Add sidebar/top navigation
- Add route structure
- Add query client provider
- Add API client layer
- Add base pages:
  - Dashboard
  - Accounts
  - Orders
  - Positions
  - Controls
  - Logs

### Deliverables
- Frontend shell with navigation and routed pages

### Exit Criteria
- Frontend boots and renders base navigation and placeholder pages

---

## Phase 6 - Frontend Paper Broker Views
### Goal
Show stock and crypto paper accounts in the UI.

### Tasks
- Build balances panels
- Build positions table
- Build orders table
- Build control forms/buttons
- Show account-level summaries
- Add loading/error/empty states

### Deliverables
- Working paper trading cockpit in the frontend

### Exit Criteria
- Frontend can display and control paper account state using backend APIs

---

## Phase 7 - Market Data Foundation
### Goal
Ingest and normalize market data for crypto and stocks.

### Tasks
- Build Kraken market data adapter
- Build Tradier market data adapter
- Define normalized candle schema
- Define quote schema
- Add symbol metadata normalization
- Store candle history
- Cache quotes in Redis where appropriate

### Deliverables
- Market data service for both asset classes

### Exit Criteria
- Backend can fetch and store normalized candles and quotes for supported symbols

---

## Phase 8 - Strategy Engine V1
### Goal
Implement deterministic momentum and trend-continuation strategies.

### Tasks
- Define strategy interface
- Implement momentum strategy
- Implement trend-continuation strategy
- Enforce closed-candle evaluation
- Add multi-timeframe confirmation support
- Persist generated signals
- Add signal reasoning payloads

### Deliverables
- V1 strategy engine producing stored signals

### Exit Criteria
- Strategies can evaluate stored market data and create signals deterministically

---

## Phase 9 - Risk Engine
### Goal
Approve or reject strategy signals using deterministic safety rules.

### Tasks
- Implement max risk per trade
- Implement exposure caps
- Implement max open positions
- Implement max daily loss guard
- Implement stale quote guard
- Implement spread sanity checks
- Add risk rejection logging

### Deliverables
- Central risk approval service

### Exit Criteria
- Signals are either approved or rejected with explicit reasons

---

## Phase 10 - Paper Execution Engine
### Goal
Convert approved signals into paper broker orders.

### Tasks
- Build execution service
- Route orders through broker interface
- Persist order/audit state changes
- Sync positions and balances after fills
- Add reconciliation logic for paper broker state

### Deliverables
- End-to-end signal-to-paper-trade flow

### Exit Criteria
- Approved signals produce paper orders and portfolio state updates

---

## Phase 11 - AI Layer V1
### Goal
Add assistive AI/ML components without making execution non-deterministic.

### Tasks
- Add regime classification
- Add signal ranking/scoring
- Add anomaly detection hooks
- Define feature generation inputs
- Store model outputs separately from hard risk decisions

### Deliverables
- AI-assisted scoring layer for filtering and ranking

### Exit Criteria
- Signals can include AI-derived metadata without bypassing deterministic rules

---

## Phase 12 - ML Scoring Engine + Historical Replay Training
### Goal
Create the historical replay, labeling, training, and validation lane that powers ML-assisted candidate ranking without changing deterministic execution behavior.

### Tasks
- Freeze historical training universes by date for stocks and crypto
- Build historical feature store rows by decision date using only information available at that time
- Add historical strategy replay/backtesting to measure follow-through outcomes
- Generate deterministic, versioned labels from replay outputs
- Define replay and backtesting policy versions
- Build reproducible training datasets from features, replay outputs, and labels
- Train baseline models per strategy
- Run walk-forward validation across unseen windows
- Review feature importance and drift
- Integrate ML follow-through scoring into ranking only after deterministic filters pass
- Add retraining schedule and model versioning
- Persist reproducibility metadata and inspection endpoints
- Add audit documentation for ML scope and guardrails

### Deliverables
- Historical replay engine and replay result persistence
- Deterministic label generation pipeline
- Reproducible ML training dataset builder
- Baseline ML model artifacts and validation reports
- Read-only ML inspection endpoints
- Audit documentation describing allowed and forbidden ML influence

### Exit Criteria
- Historical replay produces deterministic labels from stored data
- ML training uses replay-derived outcomes rather than guessed returns
- Walk-forward validation is strong enough to justify ranking use
- ML improves candidate ranking without bypassing deterministic strategy, risk, or execution rules
- Model scores are reproducible and inspectable

---

## Phase 13 - Live Broker Adapters
### Goal
Introduce live broker connectivity behind the same broker abstraction.

### Tasks
- Implement Kraken live broker adapter
- Implement Tradier live broker adapter
- Add broker order translation
- Add broker state synchronization
- Add live/paper mode separation
- Add reconciliation and drift detection

### Deliverables
- Live broker adapters behind shared interfaces

### Exit Criteria
- Live accounts can be queried and orders can be routed through adapter boundaries

---

## Phase 14 - Observability and Runtime Controls
### Goal
Make the system traceable, inspectable, and safer to operate.

### Tasks
- Add structured logs
- Add audit endpoints/pages
- Add broker health visibility
- Add risk status visibility
- Add runtime strategy enable/disable controls
- Add worker/scheduler health views

### Deliverables
- Operational visibility layer

### Exit Criteria
- Operators can inspect system state without digging through raw DB tables

---

## Phase 15 - Backtesting and Research
### Goal
Create a research lane separate from live/paper execution.

### Tasks
- Add historical replay runner
- Add backtest metrics
- Add walk-forward evaluation support
- Add parameter testing hooks
- Add result persistence

### Deliverables
- Research/backtesting module

### Exit Criteria
- Strategies can be evaluated on historical data with stored metrics

---

## Phase 16 - Production Hardening
### Goal
Prepare the platform for safer long-running operation.

### Tasks
- Add bounded retries
- Add circuit breakers
- Add startup validation
- Add configuration validation
- Add data integrity checks
- Add deployment sanity checks
- Add backup and recovery notes

### Deliverables
- Hardened runtime baseline

### Exit Criteria
- The system handles expected failure cases cleanly and predictably
