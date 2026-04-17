# ENGINEERING_STANDARD.md

## Purpose

This document defines the mandatory engineering standards for AI-Trader-v1.

The system must remain:

- deterministic
- testable
- modular
- async-safe
- observable
- broker-agnostic
- production-ready

---

## Core Design Philosophy

Treat the platform as a control system, not a guessing engine.

Every trading decision must be:

- explainable
- auditable
- reproducible
- observable

AI may assist with scoring, filtering, and regime detection, but execution and risk rules must remain deterministic.

---

## Technology Stack

### Backend
- Python 3.12
- FastAPI
- SQLAlchemy 2.x
- Alembic
- PostgreSQL
- Redis
- pytest

### Frontend
- React
- TypeScript
- Tailwind CSS
- TanStack Query
- TanStack Table
- lucide-react

### Infrastructure
- Docker Compose

---

## Concurrency Standard

| Task Type | Recommended Approach |
|---|---|
| I/O-bound, async-friendly libs | Asyncio |
| I/O-bound, blocking libs | Thread workers |
| CPU-bound | Multiprocessing |

### Rule of thumb

- Use async if the libraries are async-compatible.
- Use threads if the code must call blocking libraries.
- Use multiprocessing for CPU-heavy workloads.

### Use asyncio for
- FastAPI endpoints
- websocket updates
- orchestration loops
- async HTTP calls
- Redis operations
- scheduler loops

### Use threads for
- blocking broker SDK calls
- blocking file I/O
- blocking CSV work
- legacy sync libraries

### Use multiprocessing for
- backtesting at scale
- ML training
- parameter sweeps
- feature generation batches

Never block the event loop with synchronous broker or long-running compute work.

---

## Python 3.12 Standards

Mandatory rules:

- Use `from datetime import UTC, datetime`
- Use `datetime.now(UTC)` instead of `datetime.utcnow()`
- Use built-in generics:
  - `list[str]`
  - `dict[str, int]`
  - `set[str]`
  - `tuple[int, ...]`
- Use union syntax:
  - `str | None`
- Import abstract collection types from `collections.abc`
- Prefer small, focused, testable modules
- All timestamps must be timezone-aware
- App/config default timezone is `America/New_York`
- Strategy evaluation must use closed candles only

Forbidden patterns:

- `datetime.utcnow()`
- `typing.Optional`
- `typing.List`
- `typing.Dict`
- naive datetimes in business logic
- oversized god-modules
- hidden mutable global state

---

## Package Structure

- `agents/` orchestration only
- `services/` business logic
- `models/` SQLAlchemy models
- `schemas/` Pydantic schemas
- `db/` engine/session/base wiring
- `brokers/` live and paper broker adapters
- `strategies/` signal generation
- `risk/` position sizing and controls
- `portfolio/` balances, positions, pnl
- `market_data/` candles, quotes, metadata
- `workers/` background loops
- `api/` FastAPI routers
- `utils/` shared helpers only when truly cross-domain

---

## Separation of Concerns

### Agents
- orchestrate workflows only
- do not contain business logic

### Services
- contain deterministic domain logic
- must be unit-testable

### Brokers
- implement a shared broker interface
- support both live and paper behavior

### Strategies
- generate signals only
- do not place orders
- do not contain broker logic

### Risk
- validates tradability
- enforces caps, sizing, and safety rules

---

## Broker Abstraction Rule

Strategy and risk code must never talk directly to Kraken or Tradier client code.

All execution must go through broker adapters behind a shared interface.

Initial adapters:

- `KrakenLiveBroker`
- `TradierLiveBroker`
- `CryptoPaperBroker`
- `StockPaperBroker`

---

## Paper Trading Requirements

Paper brokers must simulate:

- balances
- buying power
- order lifecycle
- fills
- positions
- realized PnL
- unrealized PnL
- fees

Paper controls must support:

- wipe account
- reset balance
- cancel orders
- close positions
- sync valuation

---

## Strategy Rules for V1

Initial strategies:

- momentum
- trend continuation

Signal rules:

- closed candles only
- no intra-candle trading decisions
- deterministic inputs
- explicit reasoning payloads

Each signal should include:

- symbol
- asset_class
- timeframe
- strategy_key
- signal_type
- confidence
- regime
- entry_price
- stop_price
- take_profit_price

---

## Risk Engine Requirements

Minimum controls:

- max risk per trade
- max open positions
- max daily loss
- per-symbol exposure cap
- per-asset-class exposure cap
- stale quote protection
- spread sanity checks
- circuit-breaker support

Risk decisions must be logged with reasons.

---

## Logging and Observability

The platform must log:

- signal generation
- signal rejection
- order submission
- order rejection
- order cancellation
- fills
- position open/close
- risk events
- broker sync errors

Logs should include:

- timestamp
- symbol when applicable
- strategy when applicable
- decision reason
- relevant IDs where available

---

## Database Standards

PostgreSQL is the source of truth.

All persisted state must be explicit.

Core entities will include:

- accounts
- balances
- orders
- fills
- positions
- signals
- risk_events

---

## Testing Standards

Every new module should be:

- Python 3.12 compliant
- import-clean
- type-hint friendly
- deterministic
- unit-testable
- small enough to review easily

At minimum, test:

- strategy logic
- risk logic
- paper broker behavior
- order lifecycle
- position updates

No tests should require live broker access.

---

## Error Handling

Do not silently swallow errors.

Errors must:

- log the reason
- include context
- surface enough detail for debugging

Retries are allowed only where safe and bounded.

---

## Determinism

The same inputs must produce the same outputs.

Hidden randomness is not allowed in execution logic.

If randomness is needed for research modules, seeds must be explicit and controlled.
