from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.ai_research import TrainingDatasetRow, TrainingDatasetVersion
from app.models.trading import AssetClass
from app.services.historical.historical_feature_importance_review import HistoricalFeatureImportanceReviewService
from app.services.historical.historical_feature_importance_review_schemas import HistoricalFeatureImportanceReviewConfig
from app.services.historical.historical_walkforward_validation_schemas import HistoricalWalkForwardValidationConfig


def _build_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed_dataset(session: Session) -> None:
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
            row_count=8,
            feature_keys_json=["feature_alpha", "feature_beta"],
            build_metadata_json={"seed": "feature_review"},
        )
    )
    start = datetime(2026, 1, 1, 10, tzinfo=UTC)
    alpha_values = [0.1, 0.9, 0.2, 1.0, 0.15, 0.95, 0.25, 1.05]
    beta_values = [0.0, 0.1, 0.0, 0.1, 5.0, 5.2, 5.1, 5.3]
    labels = [0, 1, 0, 1, 0, 1, 0, 1]
    for index, (alpha, beta, label) in enumerate(zip(alpha_values, beta_values, labels, strict=True)):
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
                    "feature_alpha": alpha,
                    "feature_beta": beta,
                },
                label_values_json={"achieved_label": bool(label)},
                metadata_json={"seed_index": index},
            )
        )
    session.commit()


def test_feature_importance_review_writes_deterministic_artifact(tmp_path: Path) -> None:
    session = _build_session()
    _seed_dataset(session)
    service = HistoricalFeatureImportanceReviewService(
        session,
        artifact_dir=tmp_path,
        config=HistoricalFeatureImportanceReviewConfig(
            validation_config=HistoricalWalkForwardValidationConfig(
                min_train_periods=4,
                validation_periods=2,
                step_periods=2,
            ),
            permutation_repeats=3,
            top_feature_count=5,
        ),
    )

    first = service.review(dataset_version="12f_dataset_v1", strategy_name="momentum")
    second = service.review(dataset_version="12f_dataset_v1", strategy_name="momentum")

    assert first.report_version == second.report_version
    assert first.global_feature_importance == second.global_feature_importance
    assert first.global_drift_metrics == second.global_drift_metrics
    assert first.artifact_path is not None
    assert Path(first.artifact_path).exists()

    artifact_payload = json.loads(Path(first.artifact_path).read_text(encoding="utf-8"))
    assert artifact_payload["dataset_version"] == "12f_dataset_v1"
    assert artifact_payload["strategy_name"] == "momentum"


def test_feature_importance_review_flags_drifted_feature() -> None:
    session = _build_session()
    _seed_dataset(session)
    service = HistoricalFeatureImportanceReviewService(
        session,
        config=HistoricalFeatureImportanceReviewConfig(
            validation_config=HistoricalWalkForwardValidationConfig(
                min_train_periods=4,
                validation_periods=2,
                step_periods=2,
            ),
            permutation_repeats=3,
            drift_psi_threshold=0.05,
            drift_mean_shift_threshold=0.25,
        ),
    )

    summary = service.review(dataset_version="12f_dataset_v1", strategy_name="momentum")

    assert summary.global_feature_importance
    assert summary.global_drift_metrics
    assert summary.drifted_features
    assert summary.drifted_features[0].feature_key == "feature_beta"
    assert summary.drifted_features[0].drift_flagged is True
    assert summary.drifted_features[0].drift_flag_reasons
