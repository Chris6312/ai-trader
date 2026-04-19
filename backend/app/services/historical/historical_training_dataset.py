from __future__ import annotations

import hashlib
import json
from bisect import bisect_right
from collections.abc import Sequence
from datetime import UTC, date

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.ai_research import (
    FeatureDefinitionVersion,
    HistoricalFeatureRow,
    HistoricalReplayLabel,
    HistoricalStrategyReplay,
    HistoricalUniverseSnapshot,
    TrainingDatasetRow,
    TrainingDatasetVersion,
)
from app.services.historical.historical_backtesting_policy import HistoricalBacktestingPolicyService
from app.services.historical.historical_training_dataset_schemas import (
    HistoricalTrainingDataset,
    TrainingDatasetBuildSummary,
    TrainingDatasetRowRecord,
    TrainingDatasetVersionRecord,
)


class HistoricalTrainingDatasetService:
    DATASET_DEFINITION_VERSION = "12f_v1"

    def __init__(
        self,
        session: Session,
        *,
        backtesting_policy_service: HistoricalBacktestingPolicyService | None = None,
        dataset: HistoricalTrainingDataset | None = None,
    ) -> None:
        self._session = session
        self._backtesting_policy_service = backtesting_policy_service or HistoricalBacktestingPolicyService(session)
        self._dataset = dataset or HistoricalTrainingDataset(
            dataset_name="baseline_training_dataset",
            dataset_definition_version=self.DATASET_DEFINITION_VERSION,
            policy_version="12e_policy_v1",
            feature_version="11c_v1",
            asset_class="stock",
            timeframe="1h",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )

    def build_dataset(
        self,
        *,
        start_date: date,
        end_date: date,
        asset_class: str,
        timeframe: str,
        policy_version: str,
        feature_version: str,
        source_label: str | None = None,
        strategy_name: str | None = None,
    ) -> TrainingDatasetBuildSummary:
        resolved_policy = self._backtesting_policy_service.resolve_policy(policy_version)
        dataset_version = self._build_dataset_version(
            start_date=start_date,
            end_date=end_date,
            asset_class=asset_class,
            timeframe=timeframe,
            policy_version=policy_version,
            feature_version=feature_version,
            source_label=source_label,
            strategy_name=strategy_name,
        )

        feature_definition = self._session.get(FeatureDefinitionVersion, feature_version)
        if feature_definition is None:
            raise ValueError(f"unknown feature_version: {feature_version}")

        replay_rows = list(
            self._session.scalars(
                select(HistoricalStrategyReplay).where(
                    HistoricalStrategyReplay.decision_date >= start_date,
                    HistoricalStrategyReplay.decision_date <= end_date,
                    HistoricalStrategyReplay.asset_class == asset_class,
                    HistoricalStrategyReplay.timeframe == timeframe,
                    HistoricalStrategyReplay.policy_version == policy_version,
                    HistoricalStrategyReplay.replay_version == resolved_policy.replay_policy_version,
                ).order_by(
                    HistoricalStrategyReplay.decision_date.asc(),
                    HistoricalStrategyReplay.symbol.asc(),
                    HistoricalStrategyReplay.strategy_name.asc(),
                    HistoricalStrategyReplay.entry_candle_time.asc(),
                )
            )
        )
        if source_label is not None:
            replay_rows = [row for row in replay_rows if row.source_label == source_label]
        if strategy_name is not None:
            replay_rows = [row for row in replay_rows if row.strategy_name == strategy_name]

        universe_rows = list(
            self._session.scalars(
                select(HistoricalUniverseSnapshot).where(
                    HistoricalUniverseSnapshot.decision_date >= start_date,
                    HistoricalUniverseSnapshot.decision_date <= end_date,
                    HistoricalUniverseSnapshot.asset_class == asset_class,
                )
            )
        )
        universe_map = {
            (row.decision_date, row.symbol, row.asset_class): row
            for row in universe_rows
        }

        label_rows = list(
            self._session.scalars(
                select(HistoricalReplayLabel).where(
                    HistoricalReplayLabel.decision_date >= start_date,
                    HistoricalReplayLabel.decision_date <= end_date,
                    HistoricalReplayLabel.asset_class == asset_class,
                    HistoricalReplayLabel.timeframe == timeframe,
                    HistoricalReplayLabel.label_version == resolved_policy.label_version,
                    HistoricalReplayLabel.replay_version == resolved_policy.replay_policy_version,
                )
            )
        )
        if source_label is not None:
            label_rows = [row for row in label_rows if row.source_label == source_label]
        if strategy_name is not None:
            label_rows = [row for row in label_rows if row.strategy_name == strategy_name]
        label_map = {
            (
                row.decision_date,
                row.symbol,
                row.asset_class,
                row.timeframe,
                row.strategy_name,
                row.entry_candle_time,
                row.source_label,
                row.label_version,
            ): row
            for row in label_rows
        }

        feature_rows = list(
            self._session.scalars(
                select(HistoricalFeatureRow).where(
                    HistoricalFeatureRow.decision_date >= start_date,
                    HistoricalFeatureRow.decision_date <= end_date,
                    HistoricalFeatureRow.asset_class == asset_class,
                    HistoricalFeatureRow.timeframe == timeframe,
                    HistoricalFeatureRow.feature_version == feature_version,
                ).order_by(HistoricalFeatureRow.candle_time.asc())
            )
        )
        if source_label is not None:
            feature_rows = [row for row in feature_rows if row.source_label == source_label]

        feature_map: dict[tuple[date, str, str, str, str | None], list[HistoricalFeatureRow]] = {}
        for row in feature_rows:
            key = (row.decision_date, row.symbol, row.asset_class, row.timeframe, row.source_label)
            feature_map.setdefault(key, []).append(row)

        built_rows: list[TrainingDatasetRowRecord] = []
        skipped_missing_universe = 0
        skipped_missing_feature = 0
        skipped_missing_label = 0

        for replay_row in replay_rows:
            universe_key = (replay_row.decision_date, replay_row.symbol, replay_row.asset_class)
            universe_row = universe_map.get(universe_key)
            if universe_row is None:
                skipped_missing_universe += 1
                continue

            label_key = (
                replay_row.decision_date,
                replay_row.symbol,
                replay_row.asset_class,
                replay_row.timeframe,
                replay_row.strategy_name,
                replay_row.entry_candle_time,
                replay_row.source_label,
                resolved_policy.label_version,
            )
            label_row = label_map.get(label_key)
            if label_row is None:
                skipped_missing_label += 1
                continue

            feature_key = (
                replay_row.decision_date,
                replay_row.symbol,
                replay_row.asset_class,
                replay_row.timeframe,
                replay_row.source_label,
            )
            candidate_features = feature_map.get(feature_key, [])
            matched_feature = self._pick_feature_row(candidate_features, replay_row.entry_candle_time)
            if matched_feature is None:
                skipped_missing_feature += 1
                continue

            row_key = self._build_row_key(
                dataset_version=dataset_version,
                decision_date=replay_row.decision_date,
                symbol=replay_row.symbol,
                asset_class=str(replay_row.asset_class),
                timeframe=replay_row.timeframe,
                strategy_name=replay_row.strategy_name,
                entry_candle_time=replay_row.entry_candle_time.isoformat(),
                source_label=replay_row.source_label,
            )

            feature_candle_time = matched_feature.candle_time
            if feature_candle_time.tzinfo is None:
                feature_candle_time = feature_candle_time.replace(tzinfo=UTC)
            else:
                feature_candle_time = feature_candle_time.astimezone(UTC)

            metadata = {
                "feature_candle_time": feature_candle_time.isoformat(),
                "universe_source_label": universe_row.source_label,
                "registry_source": universe_row.registry_source,
                "history_status": universe_row.history_status,
                "is_tradable": universe_row.is_tradable,
                "replay_policy_version": replay_row.policy_version,
                "backtesting_policy_version": resolved_policy.policy_version,
                "exit_reason": replay_row.exit_reason,
                "hold_bars": replay_row.hold_bars,
                "risk_approved": replay_row.risk_approved,
            }
            built_rows.append(
                TrainingDatasetRowRecord(
                    dataset_version=dataset_version,
                    row_key=row_key,
                    decision_date=replay_row.decision_date,
                    symbol=replay_row.symbol,
                    asset_class=replay_row.asset_class,
                    timeframe=replay_row.timeframe,
                    strategy_name=replay_row.strategy_name,
                    source_label=replay_row.source_label,
                    entry_candle_time=replay_row.entry_candle_time,
                    feature_version=feature_version,
                    replay_version=resolved_policy.replay_policy_version,
                    label_version=resolved_policy.label_version,
                    feature_values=dict(matched_feature.values_json),
                    label_values=dict(label_row.label_values_json),
                    metadata=metadata,
                )
            )

        rows_replaced = self.persist_dataset(
            dataset_version=dataset_version,
            dataset_name=self._dataset.dataset_name,
            dataset_definition_version=self._dataset.dataset_definition_version,
            asset_class=asset_class,
            timeframe=timeframe,
            source_label=source_label,
            strategy_name=strategy_name,
            start_date=start_date,
            end_date=end_date,
            policy_version=policy_version,
            feature_version=feature_version,
            replay_version=resolved_policy.replay_policy_version,
            label_version=resolved_policy.label_version,
            feature_keys=list(feature_definition.feature_keys_json),
            build_metadata={
                "rows_considered": len(replay_rows),
                "rows_skipped_missing_universe": skipped_missing_universe,
                "rows_skipped_missing_feature": skipped_missing_feature,
                "rows_skipped_missing_label": skipped_missing_label,
            },
            rows=built_rows,
        )

        return TrainingDatasetBuildSummary(
            dataset_version=dataset_version,
            dataset_name=self._dataset.dataset_name,
            dataset_definition_version=self._dataset.dataset_definition_version,
            asset_class=asset_class,
            timeframe=timeframe,
            policy_version=policy_version,
            feature_version=feature_version,
            replay_version=resolved_policy.replay_policy_version,
            label_version=resolved_policy.label_version,
            source_label=source_label,
            strategy_name=strategy_name,
            start_date=start_date,
            end_date=end_date,
            rows_considered=len(replay_rows),
            rows_built=len(built_rows),
            rows_replaced=rows_replaced,
            rows_skipped_missing_universe=skipped_missing_universe,
            rows_skipped_missing_feature=skipped_missing_feature,
            rows_skipped_missing_label=skipped_missing_label,
        )

    def persist_dataset(
        self,
        *,
        dataset_version: str,
        dataset_name: str,
        dataset_definition_version: str,
        asset_class: str,
        timeframe: str,
        source_label: str | None,
        strategy_name: str | None,
        start_date: date,
        end_date: date,
        policy_version: str,
        feature_version: str,
        replay_version: str,
        label_version: str,
        feature_keys: Sequence[str],
        build_metadata: dict[str, object],
        rows: Sequence[TrainingDatasetRowRecord],
    ) -> int:
        replaced = self._replace_existing_dataset(dataset_version)
        version = self._session.get(TrainingDatasetVersion, dataset_version)
        if version is None:
            version = TrainingDatasetVersion(
                dataset_version=dataset_version,
                dataset_name=dataset_name,
                dataset_definition_version=dataset_definition_version,
                asset_class=asset_class,
                timeframe=timeframe,
                source_label=source_label,
                strategy_name=strategy_name,
                start_date=start_date,
                end_date=end_date,
                policy_version=policy_version,
                feature_version=feature_version,
                replay_version=replay_version,
                label_version=label_version,
                row_count=len(rows),
                feature_keys_json=list(feature_keys),
                build_metadata_json=dict(build_metadata),
            )
            self._session.add(version)
        else:
            version.row_count = len(rows)
            version.feature_keys_json = list(feature_keys)
            version.build_metadata_json = dict(build_metadata)
            version.policy_version = policy_version
            version.feature_version = feature_version
            version.replay_version = replay_version
            version.label_version = label_version
            version.source_label = source_label
            version.strategy_name = strategy_name
            version.start_date = start_date
            version.end_date = end_date

        for row in rows:
            self._session.add(
                TrainingDatasetRow(
                    dataset_version=row.dataset_version,
                    row_key=row.row_key,
                    decision_date=row.decision_date,
                    symbol=row.symbol,
                    asset_class=row.asset_class,
                    timeframe=row.timeframe,
                    strategy_name=row.strategy_name,
                    source_label=row.source_label,
                    entry_candle_time=row.entry_candle_time,
                    feature_version=row.feature_version,
                    replay_version=row.replay_version,
                    label_version=row.label_version,
                    feature_values_json=dict(row.feature_values),
                    label_values_json=dict(row.label_values),
                    metadata_json=dict(row.metadata),
                )
            )
        self._session.flush()
        return replaced

    def list_dataset_rows(self, dataset_version: str) -> list[TrainingDatasetRowRecord]:
        rows = list(
            self._session.scalars(
                select(TrainingDatasetRow).where(
                    TrainingDatasetRow.dataset_version == dataset_version,
                ).order_by(
                    TrainingDatasetRow.decision_date.asc(),
                    TrainingDatasetRow.symbol.asc(),
                    TrainingDatasetRow.strategy_name.asc(),
                    TrainingDatasetRow.entry_candle_time.asc(),
                )
            )
        )
        return [
            TrainingDatasetRowRecord(
                dataset_version=row.dataset_version,
                row_key=row.row_key,
                decision_date=row.decision_date,
                symbol=row.symbol,
                asset_class=row.asset_class,
                timeframe=row.timeframe,
                strategy_name=row.strategy_name,
                source_label=row.source_label,
                entry_candle_time=row.entry_candle_time,
                feature_version=row.feature_version,
                replay_version=row.replay_version,
                label_version=row.label_version,
                feature_values=dict(row.feature_values_json),
                label_values=dict(row.label_values_json),
                metadata=dict(row.metadata_json),
            )
            for row in rows
        ]

    def list_dataset_versions(self) -> list[TrainingDatasetVersionRecord]:
        rows = list(
            self._session.scalars(
                select(TrainingDatasetVersion).order_by(
                    TrainingDatasetVersion.created_at.asc(),
                    TrainingDatasetVersion.dataset_version.asc(),
                )
            )
        )
        return [
            TrainingDatasetVersionRecord(
                dataset_version=row.dataset_version,
                dataset_name=row.dataset_name,
                dataset_definition_version=row.dataset_definition_version,
                asset_class=row.asset_class,
                timeframe=row.timeframe,
                source_label=row.source_label,
                strategy_name=row.strategy_name,
                start_date=row.start_date,
                end_date=row.end_date,
                policy_version=row.policy_version,
                feature_version=row.feature_version,
                replay_version=row.replay_version,
                label_version=row.label_version,
                row_count=row.row_count,
                feature_keys=list(row.feature_keys_json),
                build_metadata=dict(row.build_metadata_json),
                created_at=row.created_at,
            )
            for row in rows
        ]

    def _replace_existing_dataset(self, dataset_version: str) -> int:
        result = self._session.execute(
            delete(TrainingDatasetRow).where(TrainingDatasetRow.dataset_version == dataset_version)
        )
        return int(result.rowcount or 0)

    def _pick_feature_row(self, rows: Sequence[HistoricalFeatureRow], entry_candle_time) -> HistoricalFeatureRow | None:
        if not rows:
            return None
        candle_times = [row.candle_time for row in rows]
        index = bisect_right(candle_times, entry_candle_time) - 1
        if index < 0:
            return None
        return rows[index]

    def _build_dataset_version(
        self,
        *,
        start_date: date,
        end_date: date,
        asset_class: str,
        timeframe: str,
        policy_version: str,
        feature_version: str,
        source_label: str | None,
        strategy_name: str | None,
    ) -> str:
        payload = {
            "asset_class": str(asset_class),
            "dataset_definition_version": self._dataset.dataset_definition_version,
            "dataset_name": self._dataset.dataset_name,
            "end_date": end_date.isoformat(),
            "feature_version": feature_version,
            "policy_version": policy_version,
            "source_label": source_label,
            "start_date": start_date.isoformat(),
            "strategy_name": strategy_name,
            "timeframe": timeframe,
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]
        return f"{self._dataset.dataset_definition_version}_{digest}"

    def _build_row_key(self, **parts: str) -> str:
        payload = json.dumps(parts, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()