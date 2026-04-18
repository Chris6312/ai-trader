from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from sqlalchemy import delete, select, tuple_
from sqlalchemy.orm import Session

from app.models.ai_research import HistoricalReplayLabel, HistoricalStrategyReplay, LabelPolicyVersion
from app.models.trading import AssetClass
from app.services.historical.historical_label_schemas import (
    HistoricalLabelGenerationSummary,
    HistoricalLabelPolicy,
    HistoricalReplayLabelRecord,
    LabelPolicyVersionRecord,
)

_DECIMAL_ZERO = Decimal("0")


class HistoricalLabelGeneratorService:
    def __init__(
        self,
        session: Session,
        *,
        policy: HistoricalLabelPolicy | None = None,
    ) -> None:
        self._session = session
        self._policy = policy or HistoricalLabelPolicy(
            label_version="12d_v1",
            policy_name="baseline_replay_success",
            success_threshold_return=Decimal("0.01"),
            max_drawdown_return=Decimal("0.02"),
            require_target_before_stop=False,
            max_hold_bars=5,
        )

    def register_label_policy(self) -> LabelPolicyVersionRecord:
        existing = self._session.get(LabelPolicyVersion, self._policy.label_version)
        if existing is None:
            existing = LabelPolicyVersion(
                label_version=self._policy.label_version,
                policy_name=self._policy.policy_name,
                success_threshold_return=self._policy.success_threshold_return,
                max_drawdown_return=self._policy.max_drawdown_return,
                require_target_before_stop=self._policy.require_target_before_stop,
                max_hold_bars=self._policy.max_hold_bars,
            )
            self._session.add(existing)
            self._session.flush()
        return LabelPolicyVersionRecord(
            label_version=existing.label_version,
            policy_name=existing.policy_name,
            success_threshold_return=existing.success_threshold_return,
            max_drawdown_return=existing.max_drawdown_return,
            require_target_before_stop=existing.require_target_before_stop,
            max_hold_bars=existing.max_hold_bars,
            created_at=existing.created_at,
        )

    def build_for_decision_date(
        self,
        *,
        decision_date: date,
        asset_class: AssetClass,
        timeframe: str,
        strategy_names: Sequence[str] | None = None,
    ) -> HistoricalLabelGenerationSummary:
        self.register_label_policy()

        statement = select(HistoricalStrategyReplay).where(
            HistoricalStrategyReplay.decision_date == decision_date,
            HistoricalStrategyReplay.asset_class == asset_class,
            HistoricalStrategyReplay.timeframe == timeframe,
            HistoricalStrategyReplay.risk_approved.is_(True),
        )
        if strategy_names:
            statement = statement.where(HistoricalStrategyReplay.strategy_name.in_(list(strategy_names)))
        statement = statement.order_by(
            HistoricalStrategyReplay.symbol.asc(),
            HistoricalStrategyReplay.strategy_name.asc(),
            HistoricalStrategyReplay.entry_candle_time.asc(),
        )
        rows = list(self._session.scalars(statement))

        records = [self._to_label_record(row) for row in rows]
        replaced = self.persist_rows(records)

        replay_version = rows[0].replay_version if rows else None
        return HistoricalLabelGenerationSummary(
            decision_date=decision_date,
            asset_class=asset_class,
            timeframe=timeframe,
            label_version=self._policy.label_version,
            replay_version=replay_version,
            rows_considered=len(rows),
            rows_labeled=len(records),
            rows_replaced=replaced,
        )

    def persist_rows(self, records: Sequence[HistoricalReplayLabelRecord]) -> int:
        items = list(records)
        replaced = self._replace_existing(items)
        for item in items:
            self._session.add(
                HistoricalReplayLabel(
                    decision_date=item.decision_date,
                    symbol=item.symbol,
                    asset_class=item.asset_class,
                    timeframe=item.timeframe,
                    strategy_name=item.strategy_name,
                    entry_candle_time=item.entry_candle_time,
                    source_label=item.source_label,
                    replay_version=item.replay_version,
                    label_version=item.label_version,
                    is_trade_profitable=item.is_trade_profitable,
                    hit_target_before_stop=item.hit_target_before_stop,
                    follow_through_strength=item.follow_through_strength,
                    drawdown_within_limit=item.drawdown_within_limit,
                    achieved_label=item.achieved_label,
                    label_values_json=item.label_values,
                )
            )
        self._session.flush()
        return replaced

    def list_rows(
        self,
        *,
        decision_date: date,
        asset_class: AssetClass,
        timeframe: str,
    ) -> list[HistoricalReplayLabelRecord]:
        rows = list(
            self._session.scalars(
                select(HistoricalReplayLabel)
                .where(
                    HistoricalReplayLabel.decision_date == decision_date,
                    HistoricalReplayLabel.asset_class == asset_class,
                    HistoricalReplayLabel.timeframe == timeframe,
                )
                .order_by(
                    HistoricalReplayLabel.symbol.asc(),
                    HistoricalReplayLabel.strategy_name.asc(),
                    HistoricalReplayLabel.entry_candle_time.asc(),
                )
            )
        )
        return [
            HistoricalReplayLabelRecord(
                decision_date=row.decision_date,
                symbol=row.symbol,
                asset_class=row.asset_class,
                timeframe=row.timeframe,
                strategy_name=row.strategy_name,
                entry_candle_time=row.entry_candle_time,
                source_label=row.source_label,
                replay_version=row.replay_version,
                label_version=row.label_version,
                is_trade_profitable=row.is_trade_profitable,
                hit_target_before_stop=row.hit_target_before_stop,
                follow_through_strength=row.follow_through_strength,
                drawdown_within_limit=row.drawdown_within_limit,
                achieved_label=row.achieved_label,
                label_values=dict(row.label_values_json),
            )
            for row in rows
        ]

    def _to_label_record(self, row: HistoricalStrategyReplay) -> HistoricalReplayLabelRecord:
        profitable = row.gross_return > _DECIMAL_ZERO
        target_first = row.exit_reason == "target_hit"
        follow_through = row.max_favorable_excursion
        max_drawdown = abs(row.max_adverse_excursion)
        drawdown_within_limit = max_drawdown <= self._policy.max_drawdown_return
        meets_return = row.gross_return >= self._policy.success_threshold_return
        within_hold_limit = row.hold_bars <= self._policy.max_hold_bars

        achieved = meets_return and drawdown_within_limit and within_hold_limit
        if self._policy.require_target_before_stop:
            achieved = achieved and target_first

        label_values = {
            "gross_return": format(row.gross_return, "f"),
            "max_favorable_excursion": format(row.max_favorable_excursion, "f"),
            "max_adverse_excursion": format(row.max_adverse_excursion, "f"),
            "hold_bars": row.hold_bars,
            "success_threshold_return": format(self._policy.success_threshold_return, "f"),
            "max_drawdown_return": format(self._policy.max_drawdown_return, "f"),
            "require_target_before_stop": self._policy.require_target_before_stop,
        }

        return HistoricalReplayLabelRecord(
            decision_date=row.decision_date,
            symbol=row.symbol,
            asset_class=row.asset_class,
            timeframe=row.timeframe,
            strategy_name=row.strategy_name,
            entry_candle_time=row.entry_candle_time,
            source_label=row.source_label,
            replay_version=row.replay_version,
            label_version=self._policy.label_version,
            is_trade_profitable=profitable,
            hit_target_before_stop=target_first,
            follow_through_strength=follow_through,
            drawdown_within_limit=drawdown_within_limit,
            achieved_label=achieved,
            label_values=label_values,
        )

    def _replace_existing(self, records: Sequence[HistoricalReplayLabelRecord]) -> int:
        if not records:
            return 0
        result = self._session.execute(
            delete(HistoricalReplayLabel).where(
                tuple_(
                    HistoricalReplayLabel.decision_date,
                    HistoricalReplayLabel.symbol,
                    HistoricalReplayLabel.asset_class,
                    HistoricalReplayLabel.timeframe,
                    HistoricalReplayLabel.strategy_name,
                    HistoricalReplayLabel.entry_candle_time,
                    HistoricalReplayLabel.label_version,
                ).in_(
                    [
                        (
                            item.decision_date,
                            item.symbol,
                            item.asset_class,
                            item.timeframe,
                            item.strategy_name,
                            item.entry_candle_time,
                            item.label_version,
                        )
                        for item in records
                    ]
                )
            )
        )
        return int(result.rowcount or 0)
