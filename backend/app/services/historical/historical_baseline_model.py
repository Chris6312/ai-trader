from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from tempfile import gettempdir
from typing import Any

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai_research import TrainingDatasetRow, TrainingDatasetVersion
from app.services.historical.historical_baseline_model_schemas import (
    BaselineModelArtifactRecord,
    BaselineModelHyperparameters,
    BaselineModelTrainingSummary,
)
from app.services.historical.historical_ml_training_utils import build_balanced_sample_weight


class HistoricalBaselineModelService:
    MODEL_FAMILY = "sklearn_gradient_boosting_classifier"
    MODEL_VERSION_PREFIX = "12g_v1"

    def __init__(
        self,
        session: Session,
        *,
        artifact_dir: str | Path | None = None,
        hyperparameters: BaselineModelHyperparameters | None = None,
    ) -> None:
        self._session = session
        self._artifact_dir = Path(artifact_dir or Path(gettempdir()) / "ai_trader_ml_artifacts")
        self._artifact_dir.mkdir(parents=True, exist_ok=True)
        self._hyperparameters = hyperparameters or BaselineModelHyperparameters()

    def train_for_dataset(
        self,
        *,
        dataset_version: str,
        strategy_name: str,
        label_key: str = "achieved_label",
    ) -> BaselineModelTrainingSummary:
        version = self._session.get(TrainingDatasetVersion, dataset_version)
        if version is None:
            raise ValueError(f"unknown dataset_version: {dataset_version}")

        rows = list(
            self._session.scalars(
                select(TrainingDatasetRow).where(
                    TrainingDatasetRow.dataset_version == dataset_version,
                    TrainingDatasetRow.strategy_name == strategy_name,
                ).order_by(
                    TrainingDatasetRow.decision_date.asc(),
                    TrainingDatasetRow.symbol.asc(),
                    TrainingDatasetRow.entry_candle_time.asc(),
                )
            )
        )

        if not rows:
            return BaselineModelTrainingSummary(
                model_version=None,
                model_family=self.MODEL_FAMILY,
                strategy_name=strategy_name,
                dataset_version=dataset_version,
                rows_considered=0,
                rows_trained=0,
                positive_rows=0,
                negative_rows=0,
                label_key=label_key,
                skipped_reason="no_rows_for_strategy",
            )

        feature_keys = [key for key in version.feature_keys_json if self._feature_key_is_usable(rows, key)]
        X, y = self._build_matrix(rows=rows, feature_keys=feature_keys, label_key=label_key)
        rows_considered = len(rows)
        rows_trained = len(y)
        positive_rows = int(sum(y))
        negative_rows = rows_trained - positive_rows

        if rows_trained < 2:
            return BaselineModelTrainingSummary(
                model_version=None,
                model_family=self.MODEL_FAMILY,
                strategy_name=strategy_name,
                dataset_version=dataset_version,
                rows_considered=rows_considered,
                rows_trained=rows_trained,
                positive_rows=positive_rows,
                negative_rows=negative_rows,
                label_key=label_key,
                feature_keys=feature_keys,
                skipped_reason="insufficient_rows",
            )

        if positive_rows == 0 or negative_rows == 0:
            return BaselineModelTrainingSummary(
                model_version=None,
                model_family=self.MODEL_FAMILY,
                strategy_name=strategy_name,
                dataset_version=dataset_version,
                rows_considered=rows_considered,
                rows_trained=rows_trained,
                positive_rows=positive_rows,
                negative_rows=negative_rows,
                label_key=label_key,
                feature_keys=feature_keys,
                skipped_reason="single_class_labels",
            )

        model = GradientBoostingClassifier(
            n_estimators=self._hyperparameters.n_estimators,
            learning_rate=self._hyperparameters.learning_rate,
            max_depth=self._hyperparameters.max_depth,
            min_samples_leaf=self._hyperparameters.min_samples_leaf,
            random_state=self._hyperparameters.random_state,
        )
        sample_weight = build_balanced_sample_weight(y)
        model.fit(X, y, sample_weight=sample_weight)

        predicted = model.predict(X)
        probability = model.predict_proba(X)[:, 1]
        train_metrics = {
            "accuracy": float(accuracy_score(y, predicted)),
            "precision": float(precision_score(y, predicted, zero_division=0)),
            "recall": float(recall_score(y, predicted, zero_division=0)),
            "roc_auc": float(roc_auc_score(y, probability)),
        }

        model_version = self._build_model_version(
            dataset_version=dataset_version,
            strategy_name=strategy_name,
            label_key=label_key,
            feature_keys=feature_keys,
            hyperparameters=self._hyperparameters,
        )
        artifact_path = self._artifact_dir / f"{model_version}.joblib"
        artifact_record = BaselineModelArtifactRecord(
            model_version=model_version,
            model_family=self.MODEL_FAMILY,
            strategy_name=strategy_name,
            dataset_version=dataset_version,
            policy_version=version.policy_version,
            feature_version=version.feature_version,
            label_version=version.label_version,
            feature_keys=feature_keys,
            label_key=label_key,
            training_window_start=version.start_date.isoformat(),
            training_window_end=version.end_date.isoformat(),
            hyperparameters=asdict(self._hyperparameters),
            train_metrics=train_metrics,
            evaluation_notes=[
                "train_metrics_are_in_sample_only",
                "use_walkforward_validation_for_promotion_and_model_health",
            ],
            artifact_path=str(artifact_path),
            trained_at=version.created_at,
        )
        joblib.dump(
            {
                "model": model,
                "artifact": artifact_record,
            },
            artifact_path,
        )

        return BaselineModelTrainingSummary(
            model_version=model_version,
            model_family=self.MODEL_FAMILY,
            strategy_name=strategy_name,
            dataset_version=dataset_version,
            rows_considered=rows_considered,
            rows_trained=rows_trained,
            positive_rows=positive_rows,
            negative_rows=negative_rows,
            label_key=label_key,
            feature_keys=feature_keys,
            metrics=train_metrics,
            artifact_path=str(artifact_path),
        )

    def load_artifact(self, artifact_path: str | Path) -> dict[str, Any]:
        return joblib.load(artifact_path)

    def _feature_key_is_usable(self, rows: list[TrainingDatasetRow], key: str) -> bool:
        for row in rows:
            value = row.feature_values_json.get(key)
            if value is None:
                return False
            try:
                float(value)
            except (TypeError, ValueError):
                return False
        return True

    def _build_matrix(
        self,
        *,
        rows: list[TrainingDatasetRow],
        feature_keys: list[str],
        label_key: str,
    ) -> tuple[np.ndarray, np.ndarray]:
        X: list[list[float]] = []
        y: list[int] = []
        for row in rows:
            label_value = row.label_values_json.get(label_key)
            if label_value is None:
                continue
            feature_vector = [float(row.feature_values_json[key]) for key in feature_keys]
            X.append(feature_vector)
            y.append(1 if bool(label_value) else 0)
        return np.asarray(X, dtype=float), np.asarray(y, dtype=int)

    def _build_model_version(
        self,
        *,
        dataset_version: str,
        strategy_name: str,
        label_key: str,
        feature_keys: list[str],
        hyperparameters: BaselineModelHyperparameters,
    ) -> str:
        payload = {
            "dataset_version": dataset_version,
            "feature_keys": feature_keys,
            "hyperparameters": asdict(hyperparameters),
            "label_key": label_key,
            "model_family": self.MODEL_FAMILY,
            "strategy_name": strategy_name,
            "version_prefix": self.MODEL_VERSION_PREFIX,
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]
        return f"{self.MODEL_VERSION_PREFIX}_{digest}"