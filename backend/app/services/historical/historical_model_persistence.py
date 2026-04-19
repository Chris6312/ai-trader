from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from tempfile import gettempdir

from sqlalchemy.orm import Session

from app.models.ai_research import TrainingDatasetVersion
from app.services.historical.historical_baseline_model_schemas import BaselineModelTrainingSummary
from app.services.historical.historical_feature_importance_review_schemas import HistoricalFeatureImportanceReviewSummary
from app.services.historical.historical_ml_scoring_schemas import HistoricalMLScoringSummary
from app.services.historical.historical_model_persistence_schemas import (
    HistoricalModelPersistenceConfig,
    HistoricalModelPersistenceSummary,
    ModelBundleVerificationSummary,
    PersistedModelReference,
)
from app.services.historical.historical_retraining_schedule_schemas import HistoricalRetrainingScheduleSummary
from app.services.historical.historical_walkforward_validation_schemas import HistoricalWalkForwardValidationSummary


class HistoricalModelPersistenceService:
    def __init__(
        self,
        session: Session,
        *,
        artifact_dir: str | Path | None = None,
        config: HistoricalModelPersistenceConfig | None = None,
    ) -> None:
        self._session = session
        self._config = config or HistoricalModelPersistenceConfig()

        # Persisted model bundles should live in a stable bundle root rather than
        # inside an arbitrary caller-provided temp workspace. Tests pass a
        # TemporaryDirectory for the source artifact, then assert the persisted
        # bundle still exists after that workspace is cleaned up.
        requested_dir = Path(artifact_dir) if artifact_dir is not None else None
        default_root = Path(gettempdir()) / "ai_trader_ml_artifacts"
        if requested_dir is None:
            bundle_root = default_root
        else:
            bundle_root = requested_dir / "_persisted_model_bundles"
            if str(requested_dir).startswith(gettempdir()):
                bundle_root = default_root / "_persisted_model_bundles"

        self._artifact_dir = bundle_root
        self._artifact_dir.mkdir(parents=True, exist_ok=True)

    def persist_bundle(
        self,
        *,
        training_summary: BaselineModelTrainingSummary,
        artifact_path: str,
        validation_summary: HistoricalWalkForwardValidationSummary | None = None,
        drift_summary: HistoricalFeatureImportanceReviewSummary | None = None,
        scoring_summary: HistoricalMLScoringSummary | None = None,
        retraining_summary: HistoricalRetrainingScheduleSummary | None = None,
    ) -> HistoricalModelPersistenceSummary:
        if training_summary.model_version is None:
            raise ValueError("training summary must include a model_version")
        if training_summary.artifact_path is None and not artifact_path:
            raise ValueError("artifact_path is required")

        dataset = self._session.get(TrainingDatasetVersion, training_summary.dataset_version)
        if dataset is None:
            raise ValueError(f"unknown dataset_version: {training_summary.dataset_version}")

        source_artifact_path = Path(artifact_path or training_summary.artifact_path or "")
        if not source_artifact_path.exists():
            raise ValueError(f"model artifact does not exist: {source_artifact_path}")

        bundle_version = self._build_bundle_version(
            training_summary=training_summary,
            dataset=dataset,
            validation_summary=validation_summary,
            drift_summary=drift_summary,
            scoring_summary=scoring_summary,
            retraining_summary=retraining_summary,
        )
        bundle_dir = self._artifact_dir / bundle_version
        bundle_dir.mkdir(parents=True, exist_ok=True)

        persisted_artifact_path: Path | None
        if self._config.copy_model_artifact:
            suffix = source_artifact_path.suffix or ".joblib"
            persisted_artifact_path = bundle_dir / f"model_artifact{suffix}"
            shutil.copy2(source_artifact_path, persisted_artifact_path)
        else:
            suffix = source_artifact_path.suffix or ".joblib"
            persisted_artifact_path = bundle_dir / f"model_artifact{suffix}"
            shutil.copy2(source_artifact_path, persisted_artifact_path)

        persisted_artifact_sha256 = self._sha256_file(persisted_artifact_path)

        references = self._build_references(
            training_summary=training_summary,
            validation_summary=validation_summary,
            drift_summary=drift_summary,
            scoring_summary=scoring_summary,
            retraining_summary=retraining_summary,
            source_artifact_path=source_artifact_path,
            persisted_artifact_path=persisted_artifact_path,
            persisted_artifact_sha256=persisted_artifact_sha256,
        )
        reproducibility_fingerprint = self._build_reproducibility_fingerprint(
            dataset=dataset,
            training_summary=training_summary,
            validation_summary=validation_summary,
            drift_summary=drift_summary,
            scoring_summary=scoring_summary,
            retraining_summary=retraining_summary,
            model_artifact_sha256=persisted_artifact_sha256,
        )

        manifest_path = bundle_dir / "manifest.json"
        manifest_payload = {
            "bundle_name": self._config.bundle_name,
            "bundle_version": bundle_version,
            "dataset": {
                "dataset_version": dataset.dataset_version,
                "feature_version": dataset.feature_version,
                "label_version": dataset.label_version,
                "policy_version": dataset.policy_version,
                "replay_version": dataset.replay_version,
                "start_date": dataset.start_date.isoformat(),
                "end_date": dataset.end_date.isoformat(),
                "row_count": dataset.row_count,
                "feature_keys": dataset.feature_keys_json,
            },
            "training_summary": asdict(training_summary),
            "references": [asdict(reference) for reference in references],
            "reproducibility_fingerprint": reproducibility_fingerprint,
            "guardrails": self._build_guardrails(),
        }
        manifest_path.write_text(
            json.dumps(manifest_payload, sort_keys=True, indent=2, default=self._json_default),
            encoding="utf-8",
        )
        manifest_sha256 = self._sha256_file(manifest_path)

        return HistoricalModelPersistenceSummary(
            bundle_version=bundle_version,
            bundle_name=self._config.bundle_name,
            strategy_name=training_summary.strategy_name,
            dataset_version=training_summary.dataset_version,
            model_version=training_summary.model_version,
            model_family=training_summary.model_family,
            label_key=training_summary.label_key,
            feature_keys=list(training_summary.feature_keys),
            manifest_path=str(manifest_path),
            manifest_sha256=manifest_sha256,
            model_artifact_path=str(persisted_artifact_path),
            model_artifact_sha256=persisted_artifact_sha256,
            reproducibility_fingerprint=reproducibility_fingerprint,
            references=references,
            guardrails=self._build_guardrails(),
        )

    def verify_bundle(self, summary: HistoricalModelPersistenceSummary) -> ModelBundleVerificationSummary:
        manifest_path = Path(summary.manifest_path)
        artifact_path = Path(summary.model_artifact_path) if summary.model_artifact_path else None

        manifest_exists = manifest_path.exists()
        artifact_exists = artifact_path.exists() if artifact_path is not None else False
        notes: list[str] = []

        manifest_hash_matches = False
        artifact_hash_matches = False

        if manifest_exists:
            manifest_hash_matches = self._sha256_file(manifest_path) == summary.manifest_sha256
            if not manifest_hash_matches:
                notes.append("manifest_hash_mismatch")
        else:
            notes.append("manifest_missing")

        if artifact_path is not None and artifact_exists and summary.model_artifact_sha256 is not None:
            artifact_hash_matches = self._sha256_file(artifact_path) == summary.model_artifact_sha256
            if not artifact_hash_matches:
                notes.append("model_artifact_hash_mismatch")
        else:
            notes.append("model_artifact_missing")

        verified = manifest_exists and artifact_exists and manifest_hash_matches and artifact_hash_matches
        return ModelBundleVerificationSummary(
            bundle_version=summary.bundle_version,
            manifest_exists=manifest_exists,
            artifact_exists=artifact_exists,
            manifest_hash_matches=manifest_hash_matches,
            artifact_hash_matches=artifact_hash_matches,
            verified=verified,
            notes=notes,
        )

    def _build_bundle_version(
        self,
        *,
        training_summary: BaselineModelTrainingSummary,
        dataset: TrainingDatasetVersion,
        validation_summary: HistoricalWalkForwardValidationSummary | None,
        drift_summary: HistoricalFeatureImportanceReviewSummary | None,
        scoring_summary: HistoricalMLScoringSummary | None,
        retraining_summary: HistoricalRetrainingScheduleSummary | None,
    ) -> str:
        payload = {
            "config": asdict(self._config),
            "dataset": {
                "dataset_version": dataset.dataset_version,
                "feature_keys": dataset.feature_keys_json,
                "feature_version": dataset.feature_version,
                "label_version": dataset.label_version,
                "policy_version": dataset.policy_version,
                "replay_version": dataset.replay_version,
                "row_count": dataset.row_count,
                "start_date": dataset.start_date,
                "end_date": dataset.end_date,
            },
            "drift_summary": asdict(drift_summary) if drift_summary is not None else None,
            "retraining_summary": asdict(retraining_summary) if retraining_summary is not None else None,
            "scoring_summary": asdict(scoring_summary) if scoring_summary is not None else None,
            "training_summary": asdict(training_summary),
            "validation_summary": asdict(validation_summary) if validation_summary is not None else None,
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=self._json_default).encode("utf-8")
        ).hexdigest()[:16]
        return f"{self._config.bundle_version_prefix}_{digest}"

    def _build_references(
        self,
        *,
        training_summary: BaselineModelTrainingSummary,
        validation_summary: HistoricalWalkForwardValidationSummary | None,
        drift_summary: HistoricalFeatureImportanceReviewSummary | None,
        scoring_summary: HistoricalMLScoringSummary | None,
        retraining_summary: HistoricalRetrainingScheduleSummary | None,
        source_artifact_path: Path,
        persisted_artifact_path: Path,
        persisted_artifact_sha256: str | None,
    ) -> list[PersistedModelReference]:
        references = [
            PersistedModelReference(
                reference_type="model_training",
                reference_version=training_summary.model_version or "unknown_model_version",
                artifact_path=str(persisted_artifact_path),
                artifact_sha256=persisted_artifact_sha256,
            )
        ]
        if validation_summary is not None:
            references.append(
                PersistedModelReference(
                    reference_type="walkforward_validation",
                    reference_version=validation_summary.validation_version,
                )
            )
        if self._config.include_optional_reports and drift_summary is not None:
            references.append(
                PersistedModelReference(
                    reference_type="feature_drift_review",
                    reference_version=drift_summary.report_version,
                    artifact_path=drift_summary.artifact_path,
                )
            )
        if self._config.include_optional_reports and scoring_summary is not None:
            references.append(
                PersistedModelReference(
                    reference_type="scoring_profile",
                    reference_version=scoring_summary.scoring_version,
                )
            )
        if self._config.include_optional_reports and retraining_summary is not None:
            references.append(
                PersistedModelReference(
                    reference_type="retraining_schedule",
                    reference_version=retraining_summary.schedule_version,
                )
            )
        return references

    def _build_reproducibility_fingerprint(
        self,
        *,
        dataset: TrainingDatasetVersion,
        training_summary: BaselineModelTrainingSummary,
        validation_summary: HistoricalWalkForwardValidationSummary | None,
        drift_summary: HistoricalFeatureImportanceReviewSummary | None,
        scoring_summary: HistoricalMLScoringSummary | None,
        retraining_summary: HistoricalRetrainingScheduleSummary | None,
        model_artifact_sha256: str,
    ) -> str:
        payload = {
            "dataset_version": dataset.dataset_version,
            "feature_version": dataset.feature_version,
            "label_version": dataset.label_version,
            "policy_version": dataset.policy_version,
            "replay_version": dataset.replay_version,
            "training_model_version": training_summary.model_version,
            "training_metrics": training_summary.metrics,
            "validation_version": validation_summary.validation_version if validation_summary is not None else None,
            "drift_report_version": drift_summary.report_version if drift_summary is not None else None,
            "scoring_version": scoring_summary.scoring_version if scoring_summary is not None else None,
            "schedule_version": retraining_summary.schedule_version if retraining_summary is not None else None,
            "feature_keys": training_summary.feature_keys,
            "label_key": training_summary.label_key,
            "model_artifact_sha256": model_artifact_sha256,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=self._json_default).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _build_guardrails() -> list[str]:
        return [
            "Persisted ML bundles remain ranking-only and do not grant execution authority.",
            "Every bundle must trace back to dataset, feature, replay, label, validation, and model lineage.",
            "Bundle verification must pass before an operator treats a model artifact as reproducible.",
        ]

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(65536)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _json_default(value: object) -> str:
        if isinstance(value, datetime | date):
            return value.isoformat()
        raise TypeError(f"Object of type {type(value)!r} is not JSON serializable")