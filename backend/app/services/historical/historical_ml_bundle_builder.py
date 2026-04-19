from __future__ import annotations

from pathlib import Path
from tempfile import gettempdir

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AssetClass
from app.models.ai_research import TrainingDatasetVersion
from app.services.historical.historical_baseline_model import HistoricalBaselineModelService
from app.services.historical.historical_feature_importance_review import HistoricalFeatureImportanceReviewService
from app.services.historical.historical_ml_bundle_builder_schemas import HistoricalMLBundleBuildSummary
from app.services.historical.historical_model_persistence import HistoricalModelPersistenceService
from app.services.historical.historical_walkforward_validation import HistoricalWalkForwardValidationService


class HistoricalMLBundleBuilderService:
    def __init__(
        self,
        session: Session,
        *,
        artifact_dir: str | Path | None = None,
    ) -> None:
        self._session = session
        self._artifact_dir = Path(artifact_dir or Path(gettempdir()) / "ai_trader_ml_artifacts")
        self._artifact_dir.mkdir(parents=True, exist_ok=True)

    def build_bundle(
        self,
        *,
        dataset_version: str | None,
        strategy_name: str | None,
        source_label: str | None = None,
        asset_class: AssetClass | None = None,
        timeframe: str | None = None,
        include_drift_review: bool = True,
    ) -> HistoricalMLBundleBuildSummary:
        dataset = self._resolve_dataset(
            dataset_version=dataset_version,
            strategy_name=strategy_name,
            source_label=source_label,
            asset_class=asset_class,
            timeframe=timeframe,
        )
        resolved_strategy_name = strategy_name or dataset.strategy_name
        if resolved_strategy_name is None or not str(resolved_strategy_name).strip():
            raise ValueError("strategy_name is required or must be present on the dataset")

        trainer = HistoricalBaselineModelService(self._session, artifact_dir=self._artifact_dir)
        training_summary = trainer.train_for_dataset(
            dataset_version=dataset.dataset_version,
            strategy_name=resolved_strategy_name,
        )
        if training_summary.model_version is None or training_summary.artifact_path is None:
            skipped_reason = training_summary.skipped_reason or "training_did_not_produce_model"
            raise ValueError(f"bundle build skipped: {skipped_reason}")

        validation_summary = HistoricalWalkForwardValidationService(self._session).validate(
            dataset_version=dataset.dataset_version,
            strategy_name=resolved_strategy_name,
        )
        drift_summary = None
        if include_drift_review:
            drift_summary = HistoricalFeatureImportanceReviewService(
                self._session,
                artifact_dir=self._artifact_dir,
            ).review(
                dataset_version=dataset.dataset_version,
                strategy_name=resolved_strategy_name,
            )

        persistence_service = HistoricalModelPersistenceService(self._session, artifact_dir=self._artifact_dir)
        persistence_summary = persistence_service.persist_bundle(
            training_summary=training_summary,
            artifact_path=training_summary.artifact_path,
            validation_summary=validation_summary,
            drift_summary=drift_summary,
        )
        verification = persistence_service.verify_bundle(persistence_summary)

        notes: list[str] = []
        if validation_summary.aggregate_metrics is not None and validation_summary.aggregate_metrics.folds_completed == 0:
            notes.append("walkforward_completed_with_zero_scored_folds")
        if drift_summary is None:
            notes.append("drift_review_skipped")

        return HistoricalMLBundleBuildSummary(
            bundle_version=persistence_summary.bundle_version,
            bundle_name=persistence_summary.bundle_name,
            dataset_version=persistence_summary.dataset_version,
            strategy_name=persistence_summary.strategy_name,
            model_version=persistence_summary.model_version,
            validation_version=validation_summary.validation_version if validation_summary is not None else None,
            drift_report_version=drift_summary.report_version if drift_summary is not None else None,
            manifest_path=persistence_summary.manifest_path,
            model_artifact_path=persistence_summary.model_artifact_path,
            verified_bundle=verification.verified,
            notes=notes + list(verification.notes),
        )

    def _resolve_dataset(
        self,
        *,
        dataset_version: str | None,
        strategy_name: str | None,
        source_label: str | None,
        asset_class: AssetClass | None,
        timeframe: str | None,
    ) -> TrainingDatasetVersion:
        if dataset_version is not None and dataset_version.strip():
            dataset = self._session.get(TrainingDatasetVersion, dataset_version)
            if dataset is None:
                raise ValueError(f"unknown dataset_version: {dataset_version}")
            return dataset

        statement = select(TrainingDatasetVersion)
        if strategy_name is not None:
            statement = statement.where(TrainingDatasetVersion.strategy_name == strategy_name)
        if source_label is not None:
            statement = statement.where(TrainingDatasetVersion.source_label == source_label)
        if asset_class is not None:
            statement = statement.where(TrainingDatasetVersion.asset_class == asset_class)
        if timeframe is not None:
            statement = statement.where(TrainingDatasetVersion.timeframe == timeframe)

        dataset = self._session.scalars(
            statement.order_by(TrainingDatasetVersion.created_at.desc(), TrainingDatasetVersion.dataset_version.desc())
        ).first()
        if dataset is None:
            raise ValueError("no matching training dataset found for live bundle build")
        return dataset
