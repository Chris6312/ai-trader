from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.ai_research import TrainingDatasetRow, TrainingDatasetVersion
from app.models.trading import AssetClass
from app.services.historical.historical_walkforward_validation import HistoricalWalkForwardValidationService
from app.services.historical.historical_walkforward_validation_schemas import HistoricalWalkForwardValidationConfig


def _build_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed_dataset(session: Session, *, positive_pattern: list[int]) -> None:
    session.add(
        TrainingDatasetVersion(
            dataset_version="12f_dataset_v1",
            dataset_name="baseline_training_dataset",
            dataset_definition_version="12f_v1",
            asset_class=AssetClass.STOCK,
            timeframe="1h",
            source_label="alpaca",
            strategy_name="momentum",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 8),
            policy_version="12e_policy_v1",
            feature_version="11c_v1",
            replay_version="12c_v1",
            label_version="12d_v1",
            row_count=len(positive_pattern),
            feature_keys_json=["feature_alpha", "feature_beta"],
            build_metadata_json={"seed": "walkforward"},
        )
    )
    start = datetime(2026, 1, 1, 10, tzinfo=UTC)
    for index, label in enumerate(positive_pattern):
        decision_day = date(2026, 1, 1) + timedelta(days=index)
        entry_time = start + timedelta(days=index)
        session.add(
            TrainingDatasetRow(
                dataset_version="12f_dataset_v1",
                row_key=f"row-{index}",
                decision_date=decision_day,
                symbol="AAPL",
                asset_class=AssetClass.STOCK,
                timeframe="1h",
                strategy_name="momentum",
                source_label="alpaca",
                entry_candle_time=entry_time,
                feature_version="11c_v1",
                replay_version="12c_v1",
                label_version="12d_v1",
                feature_values_json={
                    "feature_alpha": float(index),
                    "feature_beta": float(index % 3),
                },
                label_values_json={"achieved_label": bool(label)},
                metadata_json={"seed_index": index},
            )
        )
    session.commit()


def test_walkforward_builds_deterministic_time_ordered_fold_plan() -> None:
    session = _build_session()
    _seed_dataset(session, positive_pattern=[0, 1, 0, 1, 0, 1, 0, 1])
    service = HistoricalWalkForwardValidationService(
        session,
        config=HistoricalWalkForwardValidationConfig(
            min_train_periods=4,
            validation_periods=2,
            step_periods=2,
        ),
    )

    fold_plan = service.build_fold_plan(dataset_version="12f_dataset_v1", strategy_name="momentum")

    assert len(fold_plan) == 2
    assert fold_plan[0].train_end_date < fold_plan[0].validation_start_date
    assert fold_plan[1].train_end_date < fold_plan[1].validation_start_date
    assert fold_plan[0] == service.build_fold_plan(dataset_version="12f_dataset_v1", strategy_name="momentum")[0]


def test_walkforward_validation_is_stable_across_repeated_runs() -> None:
    session = _build_session()
    _seed_dataset(session, positive_pattern=[0, 1, 0, 1, 0, 1, 0, 1])
    service = HistoricalWalkForwardValidationService(
        session,
        config=HistoricalWalkForwardValidationConfig(
            min_train_periods=4,
            validation_periods=2,
            step_periods=2,
        ),
    )

    first = service.validate(dataset_version="12f_dataset_v1", strategy_name="momentum")
    second = service.validate(dataset_version="12f_dataset_v1", strategy_name="momentum")

    assert first.validation_version == second.validation_version
    assert first.aggregate_metrics == second.aggregate_metrics
    assert [fold.metrics for fold in first.folds] == [fold.metrics for fold in second.folds]


def test_walkforward_skips_single_class_training_windows_cleanly() -> None:
    session = _build_session()
    _seed_dataset(session, positive_pattern=[0, 0, 0, 0, 1, 1, 0, 1])
    service = HistoricalWalkForwardValidationService(
        session,
        config=HistoricalWalkForwardValidationConfig(
            min_train_periods=4,
            validation_periods=2,
            step_periods=2,
        ),
    )

    summary = service.validate(dataset_version="12f_dataset_v1", strategy_name="momentum")

    assert summary.folds[0].skipped_reason == "single_class_training_rows"
    assert summary.aggregate_metrics is not None
    assert summary.aggregate_metrics.folds_skipped >= 1
