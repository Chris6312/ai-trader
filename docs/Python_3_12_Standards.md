# Python 3.12 Standards

This repository targets Python 3.12+.

These standards are mandatory for all backend code.

## Required rules

- Use `from datetime import UTC, datetime`
- Use `datetime.now(UTC)` instead of `datetime.utcnow()`
- Use modern built-in generics:
  - `list[str]`
  - `dict[str, int]`
  - `set[str]`
  - `tuple[int, ...]`
- Use union syntax:
  - `str | None`
  - not `Optional[str]`
- Import abstract collection types from `collections.abc`
  - `Callable`
  - `Iterable`
  - `Mapping`
  - `Sequence`
- Prefer explicit, narrow type aliases where useful
- Avoid duplicate helper utilities across modules
- Keep business logic out of agents
- Keep orchestration logic out of domain services
- All new code must be timezone-aware
- All timestamps default to America/New_York at the app/config layer
- All persisted timestamps must be explicit and consistent
- Closed-candle logic only for strategy evaluation
- New modules must be small, focused, and testable

## Forbidden patterns

- `datetime.utcnow()`
- `typing.Optional`
- `typing.List`
- `typing.Dict`
- `typing.Tuple`
- duplicated decimal clamp/quantize helpers
- oversized god-modules
- hidden mutable global state
- naive datetimes in business logic

## Package structure expectations

- `agents/` orchestrates
- `services/` contains business logic
- `models/` contains DB models
- `schemas/` contains Pydantic contracts
- `db/` contains engine/session/base wiring
- `utils/` contains shared helpers only when truly cross-domain

## Quality bar

Every new backend file should be:

- Python 3.12 compliant
- import-clean
- type-hint friendly
- deterministic
- unit-testable
- small enough to review without scrolling through a novel