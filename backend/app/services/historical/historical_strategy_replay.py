from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, date
from decimal import Decimal

from sqlalchemy import delete, select, tuple_
from sqlalchemy.orm import Session

from app.models.ai_research import HistoricalStrategyReplay, HistoricalUniverseSnapshot
from app.risk.approval import DeterministicRiskApprovalService
from app.risk.types import RiskApprovalInput
from app.services.historical.historical_replay_schemas import (
    HistoricalReplayCandidate,
    HistoricalReplayPolicy,
    HistoricalReplayRecord,
    HistoricalReplaySummary,
)
from app.services.historical.schemas import HistoricalCandleRecord
from app.strategies.momentum import MomentumStrategy
from app.strategies.trend_continuation import TrendContinuationStrategy
from app.strategies.types import Candle, StrategyInputBundle, StrategyResult

_DECIMAL_ZERO = Decimal("0")
_DEFAULT_ACCOUNT_EQUITY = Decimal("100000")
_DEFAULT_PROPOSED_NOTIONAL = Decimal("1000")
_DEFAULT_MAX_OPEN_POSITIONS = 5
_DEFAULT_MAX_TOTAL_EXPOSURE_PERCENT = Decimal("100")
_DEFAULT_MAX_SYMBOL_EXPOSURE_PERCENT = Decimal("25")
_DEFAULT_MAX_DAILY_LOSS_PERCENT = Decimal("10")
_DEFAULT_MAX_SPREAD_PERCENT = Decimal("1")


class HistoricalStrategyReplayService:
    REPLAY_VERSION = "12c_v1"

    def __init__(
        self,
        session: Session,
        *,
        risk_service: DeterministicRiskApprovalService | None = None,
        policy: HistoricalReplayPolicy | None = None,
    ) -> None:
        self._session = session
        self._risk_service = risk_service or DeterministicRiskApprovalService()
        self._policy = policy or HistoricalReplayPolicy(
            policy_version="12c_policy_v1",
            target_r_multiple=Decimal("2"),
            max_hold_bars=5,
        )
        self._strategies = {
            "momentum": MomentumStrategy(),
            "trend_continuation": TrendContinuationStrategy(),
        }

    def replay_for_decision_date(
        self,
        *,
        decision_date: date,
        asset_class: str,
        timeframe: str,
        source_label: str,
        candles_by_symbol: Mapping[str, Sequence[HistoricalCandleRecord]],
        strategy_names: Sequence[str] | None = None,
    ) -> HistoricalReplaySummary:
        selected_strategy_names = list(strategy_names or self._strategies.keys())
        for strategy_name in selected_strategy_names:
            if strategy_name not in self._strategies:
                raise ValueError(f"unsupported replay strategy: {strategy_name}")

        universe_rows = list(
            self._session.scalars(
                select(HistoricalUniverseSnapshot).where(
                    HistoricalUniverseSnapshot.decision_date == decision_date,
                    HistoricalUniverseSnapshot.asset_class == asset_class,
                ).order_by(HistoricalUniverseSnapshot.symbol.asc())
            )
        )

        entries_evaluated = 0
        entries_approved = 0
        replay_records: list[HistoricalReplayRecord] = []

        for universe_row in universe_rows:
            candles = [
                candle
                for candle in candles_by_symbol.get(universe_row.symbol, ())
                if candle.timeframe == timeframe and candle.source_label == source_label
            ]
            if not candles:
                continue

            ordered = sorted(candles, key=lambda item: item.candle_time)

            for strategy_name in selected_strategy_names:
                candidate = self._build_first_candidate_for_symbol_strategy(
                    decision_date=decision_date,
                    strategy_name=strategy_name,
                    candles=ordered,
                )
                if candidate is None:
                    continue

                entries_evaluated += 1

                if not candidate.risk_result.approved:
                    continue

                entries_approved += 1
                replay_records.append(
                    self._resolve_trade(
                        candidate=candidate,
                        candles=ordered,
                    )
                )

        rows_replaced = self.persist_rows(decision_date=decision_date, records=replay_records)

        return HistoricalReplaySummary(
            decision_date=decision_date,
            asset_class=asset_class,
            timeframe=timeframe,
            source_label=source_label,
            replay_version=self.REPLAY_VERSION,
            policy_version=self._policy.policy_version,
            symbols_requested=len(universe_rows),
            entries_evaluated=entries_evaluated,
            entries_approved=entries_approved,
            trades_persisted=len(replay_records),
            rows_replaced=rows_replaced,
        )

    def persist_rows(
        self,
        *,
        decision_date: date,
        records: Sequence[HistoricalReplayRecord],
    ) -> int:
        items = list(records)
        replaced = self._replace_existing(decision_date=decision_date, records=items)

        for item in items:
            self._session.add(
                HistoricalStrategyReplay(
                    decision_date=item.decision_date,
                    symbol=item.symbol,
                    asset_class=item.asset_class,
                    timeframe=item.timeframe,
                    strategy_name=item.strategy_name,
                    source_label=item.source_label,
                    replay_version=item.replay_version,
                    policy_version=item.policy_version,
                    entry_candle_time=item.entry_candle_time,
                    exit_candle_time=item.exit_candle_time,
                    entry_price=item.entry_price,
                    exit_price=item.exit_price,
                    stop_price=item.stop_price,
                    target_price=item.target_price,
                    entry_confidence=item.entry_confidence,
                    risk_approved=item.risk_approved,
                    exit_reason=item.exit_reason,
                    hold_bars=item.hold_bars,
                    max_favorable_excursion=item.max_favorable_excursion,
                    max_adverse_excursion=item.max_adverse_excursion,
                    gross_return=item.gross_return,
                    strategy_summary=item.strategy_summary,
                    strategy_checks_json=item.strategy_checks,
                    strategy_indicators_json=item.strategy_indicators,
                    risk_rejection_reason=item.risk_rejection_reason,
                )
            )

        self._session.flush()
        return replaced

    def list_rows(
        self,
        *,
        decision_date: date,
        asset_class: str,
        timeframe: str,
    ) -> list[HistoricalReplayRecord]:
        rows = list(
            self._session.scalars(
                select(HistoricalStrategyReplay).where(
                    HistoricalStrategyReplay.decision_date == decision_date,
                    HistoricalStrategyReplay.asset_class == asset_class,
                    HistoricalStrategyReplay.timeframe == timeframe,
                ).order_by(
                    HistoricalStrategyReplay.symbol.asc(),
                    HistoricalStrategyReplay.strategy_name.asc(),
                    HistoricalStrategyReplay.entry_candle_time.asc(),
                )
            )
        )

        return [
            HistoricalReplayRecord(
                decision_date=row.decision_date,
                symbol=row.symbol,
                asset_class=row.asset_class,
                timeframe=row.timeframe,
                strategy_name=row.strategy_name,
                source_label=row.source_label,
                replay_version=row.replay_version,
                policy_version=row.policy_version,
                entry_candle_time=row.entry_candle_time,
                exit_candle_time=row.exit_candle_time,
                entry_price=row.entry_price,
                exit_price=row.exit_price,
                stop_price=row.stop_price,
                target_price=row.target_price,
                entry_confidence=row.entry_confidence,
                risk_approved=row.risk_approved,
                exit_reason=row.exit_reason,
                hold_bars=row.hold_bars,
                max_favorable_excursion=row.max_favorable_excursion,
                max_adverse_excursion=row.max_adverse_excursion,
                gross_return=row.gross_return,
                strategy_summary=row.strategy_summary,
                strategy_checks=dict(row.strategy_checks_json),
                strategy_indicators=dict(row.strategy_indicators_json),
                risk_rejection_reason=row.risk_rejection_reason,
            )
            for row in rows
        ]

    def _build_first_candidate_for_symbol_strategy(
        self,
        *,
        decision_date: date,
        strategy_name: str,
        candles: Sequence[HistoricalCandleRecord],
    ) -> HistoricalReplayCandidate | None:
        strategy = self._strategies[strategy_name]

        for index, entry_candle in enumerate(candles):
            if entry_candle.candle_time.date() != decision_date:
                continue

            strategy_bundle = StrategyInputBundle(
                symbol=entry_candle.symbol,
                asset_class=entry_candle.asset_class,
                primary_timeframe=entry_candle.timeframe,
                candles=[self._to_strategy_candle(item) for item in candles[: index + 1]],
                confirmation=None,
            )
            result: StrategyResult = strategy.evaluate(strategy_bundle)
            if not result.passed:
                continue

            entry_price = entry_candle.close
            stop_price = entry_candle.low
            risk_per_unit = entry_price - stop_price
            if risk_per_unit <= _DECIMAL_ZERO:
                continue

            target_price = entry_price + (risk_per_unit * self._policy.target_r_multiple)

            risk_result = self._risk_service.approve(
                RiskApprovalInput(
                    symbol=entry_candle.symbol,
                    asset_class=entry_candle.asset_class,
                    account_equity=_DEFAULT_ACCOUNT_EQUITY,
                    proposed_notional_value=_DEFAULT_PROPOSED_NOTIONAL,
                    proposed_risk_amount=risk_per_unit,
                    quote_bid=entry_price,
                    quote_ask=entry_price,
                    quote_age_seconds=0,
                    open_positions=[],
                    max_open_positions=_DEFAULT_MAX_OPEN_POSITIONS,
                    max_total_exposure_percent=_DEFAULT_MAX_TOTAL_EXPOSURE_PERCENT,
                    max_symbol_exposure_percent=_DEFAULT_MAX_SYMBOL_EXPOSURE_PERCENT,
                    max_daily_loss_percent=_DEFAULT_MAX_DAILY_LOSS_PERCENT,
                    realized_pnl_today=_DECIMAL_ZERO,
                    max_quote_age_seconds=60,
                    max_spread_percent=_DEFAULT_MAX_SPREAD_PERCENT,
                )
            )

            return HistoricalReplayCandidate(
                symbol=entry_candle.symbol,
                asset_class=entry_candle.asset_class,
                timeframe=entry_candle.timeframe,
                decision_date=entry_candle.candle_time.date(),
                entry_candle_time=entry_candle.candle_time,
                entry_price=entry_price,
                stop_price=stop_price,
                target_price=target_price,
                strategy_result=result,
                risk_result=risk_result,
                source_label=entry_candle.source_label,
                replay_version=self.REPLAY_VERSION,
                policy_version=self._policy.policy_version,
            )

        return None

    def _resolve_trade(
        self,
        *,
        candidate: HistoricalReplayCandidate,
        candles: Sequence[HistoricalCandleRecord],
    ) -> HistoricalReplayRecord:
        entry_index = next(
            (
                index
                for index, candle in enumerate(candles)
                if candle.candle_time == candidate.entry_candle_time
            ),
            None,
        )
        if entry_index is None:
            raise ValueError("candidate entry candle was not found in replay candle set")

        future_window = list(candles[entry_index + 1 : entry_index + 1 + self._policy.max_hold_bars])

        if not future_window:
            exit_candle = candles[entry_index]
            exit_reason = "no_forward_bars"
            exit_price = candidate.entry_price
            hold_bars = 0
            mfe = _DECIMAL_ZERO
            mae = _DECIMAL_ZERO
        else:
            exit_candle = future_window[-1]
            exit_reason = "time_expired"
            exit_price = exit_candle.close
            hold_bars = len(future_window)
            mfe = _DECIMAL_ZERO
            mae = _DECIMAL_ZERO

            for offset, candle in enumerate(future_window, start=1):
                favorable = (candle.high - candidate.entry_price) / candidate.entry_price
                adverse = (candle.low - candidate.entry_price) / candidate.entry_price

                if favorable > mfe:
                    mfe = favorable
                if adverse < mae:
                    mae = adverse

                if candle.low <= candidate.stop_price:
                    exit_candle = candle
                    exit_reason = "stop_hit"
                    exit_price = candidate.stop_price
                    hold_bars = offset
                    break

                if candle.high >= candidate.target_price:
                    exit_candle = candle
                    exit_reason = "target_hit"
                    exit_price = candidate.target_price
                    hold_bars = offset
                    break

        gross_return = (
            (exit_price - candidate.entry_price) / candidate.entry_price
            if candidate.entry_price > _DECIMAL_ZERO
            else _DECIMAL_ZERO
        )

        return HistoricalReplayRecord(
            decision_date=candidate.decision_date,
            symbol=candidate.symbol,
            asset_class=candidate.asset_class,
            timeframe=candidate.timeframe,
            strategy_name=candidate.strategy_result.strategy,
            source_label=candidate.source_label,
            replay_version=candidate.replay_version,
            policy_version=candidate.policy_version,
            entry_candle_time=candidate.entry_candle_time,
            exit_candle_time=exit_candle.candle_time,
            entry_price=candidate.entry_price,
            exit_price=exit_price,
            stop_price=candidate.stop_price,
            target_price=candidate.target_price,
            entry_confidence=Decimal(str(candidate.strategy_result.confidence)),
            risk_approved=candidate.risk_result.approved,
            exit_reason=exit_reason,
            hold_bars=hold_bars,
            max_favorable_excursion=mfe,
            max_adverse_excursion=mae,
            gross_return=gross_return,
            strategy_summary=candidate.strategy_result.reasoning.summary,
            strategy_checks=dict(candidate.strategy_result.reasoning.checks),
            strategy_indicators=dict(candidate.strategy_result.reasoning.indicators),
            risk_rejection_reason=(
                candidate.risk_result.rejection_reason.value
                if candidate.risk_result.rejection_reason
                else None
            ),
        )

    def _replace_existing(
        self,
        *,
        decision_date: date,
        records: Sequence[HistoricalReplayRecord],
    ) -> int:
        if not records:
            return 0

        result = self._session.execute(
            delete(HistoricalStrategyReplay).where(
                tuple_(
                    HistoricalStrategyReplay.decision_date,
                    HistoricalStrategyReplay.symbol,
                    HistoricalStrategyReplay.asset_class,
                    HistoricalStrategyReplay.timeframe,
                    HistoricalStrategyReplay.strategy_name,
                    HistoricalStrategyReplay.entry_candle_time,
                    HistoricalStrategyReplay.replay_version,
                ).in_(
                    [
                        (
                            decision_date,
                            item.symbol,
                            item.asset_class,
                            item.timeframe,
                            item.strategy_name,
                            item.entry_candle_time,
                            item.replay_version,
                        )
                        for item in records
                    ]
                )
            )
        )
        return int(result.rowcount or 0)

    def _to_strategy_candle(self, candle: HistoricalCandleRecord) -> Candle:
        return Candle(
            timestamp=candle.candle_time.astimezone(UTC),
            open=float(candle.open),
            high=float(candle.high),
            low=float(candle.low),
            close=float(candle.close),
            volume=float(candle.volume),
        )