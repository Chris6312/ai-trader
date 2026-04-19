from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from tempfile import gettempdir

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sqlalchemy.orm import Session

from app.models.ai_research import TrainingDatasetRow, TrainingDatasetVersion
from app.services.historical.historical_baseline_model_schemas import BaselineModelHyperparameters
from app.services.historical.historical_feature_importance_review_schemas import (
    FeatureDriftRecord,
    FeatureImportanceFoldReview,
    FeatureImportanceRecord,
    HistoricalFeatureImportanceReviewConfig,
    HistoricalFeatureImportanceReviewSummary,
)
from app.services.historical.historical_walkforward_validation import HistoricalWalkForwardValidationService


class HistoricalFeatureImportanceReviewService:
    MODEL_FAMILY = "sklearn_gradient_boosting_classifier"

    def __init__(
        self,
        session: Session,
        *,
        artifact_dir: str | Path | None = None,
        config: HistoricalFeatureImportanceReviewConfig | None = None,
        hyperparameters: BaselineModelHyperparameters | None = None,
    ) -> None:
        self._session = session
        self._artifact_dir = Path(artifact_dir or Path(gettempdir()) / "ai_trader_ml_artifacts")
        self._artifact_dir.mkdir(parents=True, exist_ok=True)
        self._config = config or HistoricalFeatureImportanceReviewConfig()
        self._hyperparameters = hyperparameters or BaselineModelHyperparameters()

    def review(
        self,
        *,
        dataset_version: str,
        strategy_name: str,
    ) -> HistoricalFeatureImportanceReviewSummary:
        dataset = self._session.get(TrainingDatasetVersion, dataset_version)
        if dataset is None:
            raise ValueError(f"unknown dataset_version: {dataset_version}")

        validation_service = HistoricalWalkForwardValidationService(
            self._session,
            config=self._config.validation_config,
            hyperparameters=self._hyperparameters,
        )
        validation_summary = validation_service.validate(
            dataset_version=dataset_version,
            strategy_name=strategy_name,
        )

        rows = validation_service._load_rows(dataset_version=dataset_version, strategy_name=strategy_name)
        feature_keys = [
            key for key in dataset.feature_keys_json if validation_service._feature_key_is_usable(rows, key)
        ]

        fold_reviews: list[FeatureImportanceFoldReview] = []
        completed_fold_importance: list[list[FeatureImportanceRecord]] = []
        completed_fold_drift: list[list[FeatureDriftRecord]] = []

        for fold in validation_summary.folds:
            train_rows = [
                row
                for row in rows
                if fold.train_start_date <= row.decision_date <= fold.train_end_date
            ]
            validation_rows = [
                row
                for row in rows
                if fold.validation_start_date <= row.decision_date <= fold.validation_end_date
            ]

            if fold.skipped_reason is not None:
                fold_reviews.append(
                    FeatureImportanceFoldReview(
                        fold_index=fold.fold_index,
                        train_start_date=fold.train_start_date.isoformat(),
                        train_end_date=fold.train_end_date.isoformat(),
                        validation_start_date=fold.validation_start_date.isoformat(),
                        validation_end_date=fold.validation_end_date.isoformat(),
                        train_row_count=fold.train_row_count,
                        validation_row_count=fold.validation_row_count,
                        skipped_reason=fold.skipped_reason,
                    )
                )
                continue

            review = self._build_fold_review(
                fold_index=fold.fold_index,
                train_start_date=fold.train_start_date,
                train_end_date=fold.train_end_date,
                validation_start_date=fold.validation_start_date,
                validation_end_date=fold.validation_end_date,
                train_rows=train_rows,
                validation_rows=validation_rows,
                feature_keys=feature_keys,
                label_key=self._config.validation_config.label_key,
            )
            fold_reviews.append(review)
            if review.skipped_reason is None:
                completed_fold_importance.append(review.feature_importance)
                completed_fold_drift.append(review.drift_metrics)

        global_feature_importance = self._aggregate_feature_importance(completed_fold_importance)
        global_drift_metrics = self._aggregate_drift_metrics(completed_fold_drift)
        drifted_features = [record for record in global_drift_metrics if record.drift_flagged]
        regime_feature_importance = [
            record for record in global_feature_importance if "regime" in record.feature_key.lower()
        ]

        report_version = self._build_report_version(
            dataset_version=dataset_version,
            strategy_name=strategy_name,
            feature_keys=feature_keys,
            validation_version=validation_summary.validation_version,
        )
        artifact_path = self._artifact_dir / f"{report_version}.json"
        summary = HistoricalFeatureImportanceReviewSummary(
            report_version=report_version,
            dataset_version=dataset_version,
            strategy_name=strategy_name,
            model_family=self.MODEL_FAMILY,
            validation_version=validation_summary.validation_version,
            feature_keys=feature_keys,
            global_feature_importance=global_feature_importance,
            regime_feature_importance=regime_feature_importance,
            global_drift_metrics=global_drift_metrics,
            drifted_features=drifted_features,
            folds=fold_reviews,
            artifact_path=str(artifact_path),
        )
        artifact_path.write_text(
            json.dumps(asdict(summary), sort_keys=True, indent=2, default=self._json_default),
            encoding="utf-8",
        )
        return summary

    def _build_fold_review(
        self,
        *,
        fold_index: int,
        train_start_date: date,
        train_end_date: date,
        validation_start_date: date,
        validation_end_date: date,
        train_rows: list[TrainingDatasetRow],
        validation_rows: list[TrainingDatasetRow],
        feature_keys: list[str],
        label_key: str,
    ) -> FeatureImportanceFoldReview:
        train_rows = [row for row in train_rows if row.label_values_json.get(label_key) is not None]
        validation_rows = [row for row in validation_rows if row.label_values_json.get(label_key) is not None]
        if len(train_rows) < 2:
            return self._skipped_fold_review(
                fold_index=fold_index,
                train_start_date=train_start_date,
                train_end_date=train_end_date,
                validation_start_date=validation_start_date,
                validation_end_date=validation_end_date,
                train_row_count=len(train_rows),
                validation_row_count=len(validation_rows),
                skipped_reason="insufficient_training_rows",
            )

        train_y = np.asarray([int(bool(row.label_values_json[label_key])) for row in train_rows], dtype=int)
        if len(set(train_y.tolist())) < 2:
            return self._skipped_fold_review(
                fold_index=fold_index,
                train_start_date=train_start_date,
                train_end_date=train_end_date,
                validation_start_date=validation_start_date,
                validation_end_date=validation_end_date,
                train_row_count=len(train_rows),
                validation_row_count=len(validation_rows),
                skipped_reason="single_class_training_rows",
            )
        if not validation_rows:
            return self._skipped_fold_review(
                fold_index=fold_index,
                train_start_date=train_start_date,
                train_end_date=train_end_date,
                validation_start_date=validation_start_date,
                validation_end_date=validation_end_date,
                train_row_count=len(train_rows),
                validation_row_count=0,
                skipped_reason="missing_validation_rows",
            )

        X_train = np.asarray(
            [[float(row.feature_values_json[key]) for key in feature_keys] for row in train_rows],
            dtype=float,
        )
        X_valid = np.asarray(
            [[float(row.feature_values_json[key]) for key in feature_keys] for row in validation_rows],
            dtype=float,
        )
        y_valid = np.asarray([int(bool(row.label_values_json[label_key])) for row in validation_rows], dtype=int)

        model = self._fit_model(X_train=X_train, y_train=train_y)
        tree_values = model.feature_importances_
        scoring = "roc_auc" if len(set(y_valid.tolist())) >= 2 else "accuracy"
        permutation = permutation_importance(
            model,
            X_valid,
            y_valid,
            n_repeats=self._config.permutation_repeats,
            random_state=self._hyperparameters.random_state,
            scoring=scoring,
        )

        feature_importance = [
            FeatureImportanceRecord(
                feature_key=feature_key,
                tree_importance=float(tree_value),
                permutation_importance=float(permutation.importances_mean[index]),
                folds_observed=1,
                mean_rank=0.0,
            )
            for index, (feature_key, tree_value) in enumerate(zip(feature_keys, tree_values, strict=True))
        ]
        feature_importance.sort(
            key=lambda item: (-item.permutation_importance, -item.tree_importance, item.feature_key),
        )
        for rank, record in enumerate(feature_importance, start=1):
            record.mean_rank = float(rank)

        drift_metrics = [
            self._build_drift_record(
                feature_key=feature_key,
                train_values=X_train[:, index],
                validation_values=X_valid[:, index],
            )
            for index, feature_key in enumerate(feature_keys)
        ]
        drift_metrics.sort(
            key=lambda item: (
                not item.drift_flagged,
                -item.standardized_mean_shift,
                -item.population_stability_index,
                item.feature_key,
            ),
        )

        return FeatureImportanceFoldReview(
            fold_index=fold_index,
            train_start_date=train_start_date.isoformat(),
            train_end_date=train_end_date.isoformat(),
            validation_start_date=validation_start_date.isoformat(),
            validation_end_date=validation_end_date.isoformat(),
            train_row_count=len(train_rows),
            validation_row_count=len(validation_rows),
            feature_importance=feature_importance[: self._config.top_feature_count],
            drift_metrics=drift_metrics[: self._config.top_feature_count],
        )

    def _fit_model(self, *, X_train: np.ndarray, y_train: np.ndarray) -> GradientBoostingClassifier:
        model = GradientBoostingClassifier(
            n_estimators=self._hyperparameters.n_estimators,
            learning_rate=self._hyperparameters.learning_rate,
            max_depth=self._hyperparameters.max_depth,
            min_samples_leaf=self._hyperparameters.min_samples_leaf,
            random_state=self._hyperparameters.random_state,
        )
        model.fit(X_train, y_train)
        return model

    def _build_drift_record(
        self,
        *,
        feature_key: str,
        train_values: np.ndarray,
        validation_values: np.ndarray,
    ) -> FeatureDriftRecord:
        train_mean = float(np.mean(train_values))
        validation_mean = float(np.mean(validation_values))
        train_std = float(np.std(train_values))
        validation_std = float(np.std(validation_values))
        pooled_std = float(max(train_std, validation_std, 1e-9))
        standardized_mean_shift = float(abs(validation_mean - train_mean) / pooled_std)
        psi = self._population_stability_index(train_values=train_values, validation_values=validation_values)

        drift_flag_reasons: list[str] = []
        if psi >= self._config.drift_psi_threshold:
            drift_flag_reasons.append("population_stability_index")
        if standardized_mean_shift >= self._config.drift_mean_shift_threshold:
            drift_flag_reasons.append("standardized_mean_shift")

        return FeatureDriftRecord(
            feature_key=feature_key,
            population_stability_index=psi,
            standardized_mean_shift=standardized_mean_shift,
            train_mean=train_mean,
            validation_mean=validation_mean,
            train_std=train_std,
            validation_std=validation_std,
            drift_flagged=bool(drift_flag_reasons),
            drift_flag_reasons=drift_flag_reasons,
        )

    def _population_stability_index(
        self,
        *,
        train_values: np.ndarray,
        validation_values: np.ndarray,
    ) -> float:
        if len(train_values) == 0 or len(validation_values) == 0:
            return 0.0

        combined = np.concatenate([train_values, validation_values]).astype(float)
        lower = float(np.min(combined))
        upper = float(np.max(combined))
        if np.isclose(lower, upper):
            return 0.0

        bin_count = min(10, max(2, len(np.unique(combined))))
        edges = np.linspace(lower, upper, num=bin_count + 1, dtype=float)
        edges[0] -= 1e-9
        edges[-1] += 1e-9

        train_hist, _ = np.histogram(train_values, bins=edges)
        validation_hist, _ = np.histogram(validation_values, bins=edges)

        train_ratio = np.clip(train_hist / max(len(train_values), 1), 1e-9, None)
        validation_ratio = np.clip(validation_hist / max(len(validation_values), 1), 1e-9, None)

        return float(np.sum((validation_ratio - train_ratio) * np.log(validation_ratio / train_ratio)))

    def _aggregate_feature_importance(
        self,
        fold_records: list[list[FeatureImportanceRecord]],
    ) -> list[FeatureImportanceRecord]:
        if not fold_records:
            return []
        aggregate: dict[str, dict[str, float]] = {}
        for records in fold_records:
            for rank, record in enumerate(records, start=1):
                bucket = aggregate.setdefault(
                    record.feature_key,
                    {
                        "tree_importance": 0.0,
                        "permutation_importance": 0.0,
                        "folds_observed": 0.0,
                        "rank_total": 0.0,
                    },
                )
                bucket["tree_importance"] += record.tree_importance
                bucket["permutation_importance"] += record.permutation_importance
                bucket["folds_observed"] += 1.0
                bucket["rank_total"] += float(rank)

        results = [
            FeatureImportanceRecord(
                feature_key=feature_key,
                tree_importance=values["tree_importance"] / values["folds_observed"],
                permutation_importance=values["permutation_importance"] / values["folds_observed"],
                folds_observed=int(values["folds_observed"]),
                mean_rank=values["rank_total"] / values["folds_observed"],
            )
            for feature_key, values in aggregate.items()
        ]
        results.sort(
            key=lambda item: (-item.permutation_importance, -item.tree_importance, item.mean_rank, item.feature_key),
        )
        return results[: self._config.top_feature_count]

    def _aggregate_drift_metrics(
        self,
        fold_records: list[list[FeatureDriftRecord]],
    ) -> list[FeatureDriftRecord]:
        if not fold_records:
            return []
        aggregate: dict[str, dict[str, object]] = {}
        for records in fold_records:
            for record in records:
                bucket = aggregate.setdefault(
                    record.feature_key,
                    {
                        "psi_total": 0.0,
                        "mean_shift_total": 0.0,
                        "train_mean_total": 0.0,
                        "validation_mean_total": 0.0,
                        "train_std_total": 0.0,
                        "validation_std_total": 0.0,
                        "count": 0,
                        "flag_reasons": set(),
                        "flagged": False,
                    },
                )
                bucket["psi_total"] += record.population_stability_index
                bucket["mean_shift_total"] += record.standardized_mean_shift
                bucket["train_mean_total"] += record.train_mean
                bucket["validation_mean_total"] += record.validation_mean
                bucket["train_std_total"] += record.train_std
                bucket["validation_std_total"] += record.validation_std
                bucket["count"] += 1
                bucket["flagged"] = bool(bucket["flagged"] or record.drift_flagged)
                flag_reasons = bucket["flag_reasons"]
                assert isinstance(flag_reasons, set)
                flag_reasons.update(record.drift_flag_reasons)

        results = []
        for feature_key, values in aggregate.items():
            count = int(values["count"])
            flag_reasons = sorted(str(reason) for reason in values["flag_reasons"])
            results.append(
                FeatureDriftRecord(
                    feature_key=feature_key,
                    population_stability_index=float(values["psi_total"] / count),
                    standardized_mean_shift=float(values["mean_shift_total"] / count),
                    train_mean=float(values["train_mean_total"] / count),
                    validation_mean=float(values["validation_mean_total"] / count),
                    train_std=float(values["train_std_total"] / count),
                    validation_std=float(values["validation_std_total"] / count),
                    drift_flagged=bool(values["flagged"]),
                    drift_flag_reasons=flag_reasons,
                )
            )
        results.sort(
            key=lambda item: (
                not item.drift_flagged,
                -item.standardized_mean_shift,
                -item.population_stability_index,
                item.feature_key,
            ),
        )
        return results[: self._config.top_feature_count]

    def _skipped_fold_review(
        self,
        *,
        fold_index: int,
        train_start_date: date,
        train_end_date: date,
        validation_start_date: date,
        validation_end_date: date,
        train_row_count: int,
        validation_row_count: int,
        skipped_reason: str,
    ) -> FeatureImportanceFoldReview:
        return FeatureImportanceFoldReview(
            fold_index=fold_index,
            train_start_date=train_start_date.isoformat(),
            train_end_date=train_end_date.isoformat(),
            validation_start_date=validation_start_date.isoformat(),
            validation_end_date=validation_end_date.isoformat(),
            train_row_count=train_row_count,
            validation_row_count=validation_row_count,
            skipped_reason=skipped_reason,
        )

    def _build_report_version(
        self,
        *,
        dataset_version: str,
        strategy_name: str,
        feature_keys: list[str],
        validation_version: str,
    ) -> str:
        payload = {
            "config": asdict(self._config),
            "dataset_version": dataset_version,
            "feature_keys": feature_keys,
            "hyperparameters": asdict(self._hyperparameters),
            "model_family": self.MODEL_FAMILY,
            "strategy_name": strategy_name,
            "validation_version": validation_version,
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=self._json_default).encode("utf-8")
        ).hexdigest()[:16]
        return f"{self._config.report_version_prefix}_{digest}"

    def _json_default(self, value: object) -> str:
        if isinstance(value, datetime | date):
            return value.isoformat()
        raise TypeError(f"Object of type {type(value)!r} is not JSON serializable")