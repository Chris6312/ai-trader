from __future__ import annotations

from datetime import UTC, date
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.ai_research import TrainingDatasetVersion
from app.models.trading import AssetClass
from app.services.historical.historical_baseline_model_schemas import BaselineModelTrainingSummary
from app.services.historical.historical_feature_importance_review_schemas import HistoricalFeatureImportanceReviewSummary
from app.services.historical.historical_model_persistence import HistoricalModelPersistenceService
from app.services.historical.historical_model_persistence_schemas import HistoricalModelPersistenceConfig
from app.services.historical.historical_walkforward_validation_schemas import (
    HistoricalWalkForwardValidationSummary,
    WalkForwardAggregateMetrics,
)


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
            build_metadata_json={"seed": "model_persistence"},
        )
    )
    session.commit()


def _training_summary(artifact_path: str) -> BaselineModelTrainingSummary:
    return BaselineModelTrainingSummary(
        model_version="12g_v1_model",
        model_family="sklearn_gradient_boosting_classifier",
        strategy_name="momentum",
        dataset_version="12f_dataset_v1",
        rows_considered=8,
        rows_trained=8,
        positive_rows=4,
        negative_rows=4,
        label_key="achieved_label",
        feature_keys=["feature_alpha", "feature_beta"],
        metrics={"accuracy": 0.75, "roc_auc": 0.81},
        artifact_path=artifact_path,
        skipped_reason=None,
    )


def _validation_summary() -> HistoricalWalkForwardValidationSummary:
    return HistoricalWalkForwardValidationSummary(
        validation_version="12h_v1_validation",
        dataset_version="12f_dataset_v1",
        strategy_name="momentum",
        model_family="sklearn_gradient_boosting_classifier",
        split_mode="anchored",
        label_key="achieved_label",
        folds=[],
        aggregate_metrics=WalkForwardAggregateMetrics(
            folds_attempted=2,
            folds_completed=2,
            folds_skipped=0,
            rows_validated=4,
            accuracy=0.75,
            precision=0.75,
            recall=0.75,
            roc_auc=0.80,
            validation_positive_rate=0.5,
        ),
    )


def _drift_summary(artifact_path: str) -> HistoricalFeatureImportanceReviewSummary:
    return HistoricalFeatureImportanceReviewSummary(
        report_version="12i_v1_review",
        dataset_version="12f_dataset_v1",
        strategy_name="momentum",
        model_family="sklearn_gradient_boosting_classifier",
        validation_version="12h_v1_validation",
        feature_keys=["feature_alpha", "feature_beta"],
        global_feature_importance=[],
        regime_feature_importance=[],
        global_drift_metrics=[],
        drifted_features=[],
        folds=[],
        artifact_path=artifact_path,
    )


def test_model_persistence_writes_reproducible_bundle_and_verifies() -> None:
    session = _build_session()
    _seed_dataset(session)
    with TemporaryDirectory() as temp_dir:
        model_path = Path(temp_dir) / "source_model.joblib"
        model_path.write_bytes(b"deterministic-model-bytes")
        drift_path = Path(temp_dir) / "12i_v1_review.json"
        drift_path.write_text("{}", encoding="utf-8")

        service = HistoricalModelPersistenceService(session, artifact_dir=temp_dir)
        summary = service.persist_bundle(
            training_summary=_training_summary(str(model_path)),
            artifact_path=str(model_path),
            validation_summary=_validation_summary(),
            drift_summary=_drift_summary(str(drift_path)),
        )
        verification = service.verify_bundle(summary)

    assert summary.bundle_version.startswith("12l_v1_")
    assert Path(summary.manifest_path).exists()
    assert Path(summary.model_artifact_path or "").exists()
    assert summary.reproducibility_fingerprint
    assert summary.references[0].reference_type == "model_training"
    assert verification.verified is True



def test_model_persistence_is_deterministic_for_same_inputs() -> None:
    session = _build_session()
    _seed_dataset(session)
    with TemporaryDirectory() as temp_dir:
        model_path = Path(temp_dir) / "source_model.joblib"
        model_path.write_bytes(b"deterministic-model-bytes")
        drift_path = Path(temp_dir) / "12i_v1_review.json"
        drift_path.write_text("{}", encoding="utf-8")

        service = HistoricalModelPersistenceService(
            session,
            artifact_dir=temp_dir,
            config=HistoricalModelPersistenceConfig(copy_model_artifact=True),
        )
        first = service.persist_bundle(
            training_summary=_training_summary(str(model_path)),
            artifact_path=str(model_path),
            validation_summary=_validation_summary(),
            drift_summary=_drift_summary(str(drift_path)),
        )
        second = service.persist_bundle(
            training_summary=_training_summary(str(model_path)),
            artifact_path=str(model_path),
            validation_summary=_validation_summary(),
            drift_summary=_drift_summary(str(drift_path)),
        )

    assert first.bundle_version == second.bundle_version
    assert first.reproducibility_fingerprint == second.reproducibility_fingerprint
    assert first.model_artifact_sha256 == second.model_artifact_sha256



def test_model_persistence_verification_detects_tampered_artifact() -> None:
    session = _build_session()
    _seed_dataset(session)
    with TemporaryDirectory() as temp_dir:
        model_path = Path(temp_dir) / "source_model.joblib"
        model_path.write_bytes(b"deterministic-model-bytes")
        service = HistoricalModelPersistenceService(session, artifact_dir=temp_dir)
        summary = service.persist_bundle(
            training_summary=_training_summary(str(model_path)),
            artifact_path=str(model_path),
            validation_summary=_validation_summary(),
        )
        Path(summary.model_artifact_path or "").write_bytes(b"tampered")
        verification = service.verify_bundle(summary)

    assert verification.verified is False
    assert "model_artifact_hash_mismatch" in verification.notes
