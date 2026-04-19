from __future__ import annotations

import hashlib
import json
from dataclasses import asdict

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai_research import TrainingDatasetRow, TrainingDatasetVersion
from app.services.historical.historical_baseline_model_schemas import BaselineModelHyperparameters
from app.services.historical.historical_ml_training_utils import build_balanced_sample_weight
from app.services.historical.historical_walkforward_validation_schemas import (
    HistoricalWalkForwardValidationConfig,
    HistoricalWalkForwardValidationSummary,
    WalkForwardAggregateMetrics,
    WalkForwardFoldPlan,
    WalkForwardFoldResult,
)


class HistoricalWalkForwardValidationService:
    MODEL_FAMILY = "sklearn_gradient_boosting_classifier"

    def __init__(
        self,
        session: Session,
        *,
        config: HistoricalWalkForwardValidationConfig | None = None,
        hyperparameters: BaselineModelHyperparameters | None = None,
    ) -> None:
        self._session = session
        self._config = config or HistoricalWalkForwardValidationConfig()
        self._hyperparameters = hyperparameters or BaselineModelHyperparameters()

    def build_fold_plan(
        self,
        *,
        dataset_version: str,
        strategy_name: str,
    ) -> list[WalkForwardFoldPlan]:
        rows = self._load_rows(dataset_version=dataset_version, strategy_name=strategy_name)
        decision_dates = sorted({row.decision_date for row in rows})
        if len(decision_dates) <= self._config.min_train_periods:
            return []

        plans: list[WalkForwardFoldPlan] = []
        train_end_idx = self._config.min_train_periods - 1
        fold_index = 1

        while True:
            validation_start_idx = train_end_idx + 1
            validation_end_idx = validation_start_idx + self._config.validation_periods - 1
            if validation_end_idx >= len(decision_dates):
                break

            if self._config.split_mode == "rolling":
                rolling_periods = self._config.rolling_train_periods or self._config.min_train_periods
                train_start_idx = max(0, train_end_idx - rolling_periods + 1)
            else:
                train_start_idx = 0

            train_dates = decision_dates[train_start_idx : train_end_idx + 1]
            validation_dates = decision_dates[validation_start_idx : validation_end_idx + 1]
            train_rows = [row for row in rows if row.decision_date in train_dates]
            validation_rows = [row for row in rows if row.decision_date in validation_dates]

            plans.append(
                WalkForwardFoldPlan(
                    fold_index=fold_index,
                    train_start_date=train_dates[0],
                    train_end_date=train_dates[-1],
                    validation_start_date=validation_dates[0],
                    validation_end_date=validation_dates[-1],
                    train_row_count=len(train_rows),
                    validation_row_count=len(validation_rows),
                )
            )

            fold_index += 1
            train_end_idx += self._config.step_periods

        return plans

    def validate(
        self,
        *,
        dataset_version: str,
        strategy_name: str,
    ) -> HistoricalWalkForwardValidationSummary:
        version = self._session.get(TrainingDatasetVersion, dataset_version)
        if version is None:
            raise ValueError(f"unknown dataset_version: {dataset_version}")

        rows = self._load_rows(dataset_version=dataset_version, strategy_name=strategy_name)
        feature_keys = [key for key in version.feature_keys_json if self._feature_key_is_usable(rows, key)]
        plans = self.build_fold_plan(dataset_version=dataset_version, strategy_name=strategy_name)
        results: list[WalkForwardFoldResult] = []
        aggregate_y_true: list[int] = []
        aggregate_y_pred: list[int] = []
        aggregate_y_proba: list[float] = []

        for plan in plans:
            train_rows = [
                row
                for row in rows
                if plan.train_start_date <= row.decision_date <= plan.train_end_date
            ]
            validation_rows = [
                row
                for row in rows
                if plan.validation_start_date <= row.decision_date <= plan.validation_end_date
            ]
            result = self._run_fold(
                plan=plan,
                train_rows=train_rows,
                validation_rows=validation_rows,
                feature_keys=feature_keys,
                label_key=self._config.label_key,
            )
            results.append(result)
            if result.skipped_reason is None:
                y_true = [int(row.label_values_json[self._config.label_key]) for row in validation_rows]
                X_valid = np.asarray(
                    [[float(row.feature_values_json[key]) for key in feature_keys] for row in validation_rows],
                    dtype=float,
                )
                model = self._fit_model(train_rows=train_rows, feature_keys=feature_keys, label_key=self._config.label_key)
                y_pred = model.predict(X_valid).tolist()
                y_proba = model.predict_proba(X_valid)[:, 1].tolist()
                aggregate_y_true.extend(y_true)
                aggregate_y_pred.extend(int(value) for value in y_pred)
                aggregate_y_proba.extend(float(value) for value in y_proba)

        aggregate_metrics = self._build_aggregate_metrics(results, aggregate_y_true, aggregate_y_pred, aggregate_y_proba)
        validation_version = self._build_validation_version(
            dataset_version=dataset_version,
            strategy_name=strategy_name,
            feature_keys=feature_keys,
        )
        return HistoricalWalkForwardValidationSummary(
            validation_version=validation_version,
            dataset_version=dataset_version,
            strategy_name=strategy_name,
            model_family=self.MODEL_FAMILY,
            split_mode=self._config.split_mode,
            label_key=self._config.label_key,
            folds=results,
            aggregate_metrics=aggregate_metrics,
        )

    def _run_fold(
        self,
        *,
        plan: WalkForwardFoldPlan,
        train_rows: list[TrainingDatasetRow],
        validation_rows: list[TrainingDatasetRow],
        feature_keys: list[str],
        label_key: str,
    ) -> WalkForwardFoldResult:
        if not train_rows:
            return self._skipped_fold(plan, feature_keys, "no_training_rows")
        if not validation_rows:
            return self._skipped_fold(plan, feature_keys, "no_validation_rows")

        train_y = [int(bool(row.label_values_json.get(label_key))) for row in train_rows if row.label_values_json.get(label_key) is not None]
        if len(train_y) < 2:
            return self._skipped_fold(plan, feature_keys, "insufficient_training_rows")
        if len(set(train_y)) < 2:
            return self._skipped_fold(plan, feature_keys, "single_class_training_rows")

        validation_y = [int(bool(row.label_values_json.get(label_key))) for row in validation_rows if row.label_values_json.get(label_key) is not None]
        if len(validation_y) < 1:
            return self._skipped_fold(plan, feature_keys, "missing_validation_labels")

        model = self._fit_model(train_rows=train_rows, feature_keys=feature_keys, label_key=label_key)
        X_valid = np.asarray(
            [[float(row.feature_values_json[key]) for key in feature_keys] for row in validation_rows],
            dtype=float,
        )
        y_true = np.asarray(validation_y, dtype=int)
        y_pred = np.asarray(model.predict(X_valid), dtype=int)
        y_proba = np.asarray(model.predict_proba(X_valid)[:, 1], dtype=float)
        metrics = {
            "accuracy": float(accuracy_score(y_true, y_pred)),
            "precision": float(precision_score(y_true, y_pred, zero_division=0)),
            "recall": float(recall_score(y_true, y_pred, zero_division=0)),
            "validation_positive_rate": float(np.mean(y_true)),
        }
        if len(set(y_true.tolist())) >= 2:
            metrics["roc_auc"] = float(roc_auc_score(y_true, y_proba))

        positive_rows = int(np.sum(y_true))
        negative_rows = int(len(y_true) - positive_rows)
        return WalkForwardFoldResult(
            fold_index=plan.fold_index,
            train_start_date=plan.train_start_date,
            train_end_date=plan.train_end_date,
            validation_start_date=plan.validation_start_date,
            validation_end_date=plan.validation_end_date,
            train_row_count=plan.train_row_count,
            validation_row_count=plan.validation_row_count,
            positive_rows=positive_rows,
            negative_rows=negative_rows,
            feature_keys=feature_keys,
            metrics=metrics,
        )

    def _fit_model(
        self,
        *,
        train_rows: list[TrainingDatasetRow],
        feature_keys: list[str],
        label_key: str,
    ) -> GradientBoostingClassifier:
        X = np.asarray(
            [[float(row.feature_values_json[key]) for key in feature_keys] for row in train_rows],
            dtype=float,
        )
        y = np.asarray(
            [int(bool(row.label_values_json[label_key])) for row in train_rows],
            dtype=int,
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
        return model

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

    def _load_rows(self, *, dataset_version: str, strategy_name: str) -> list[TrainingDatasetRow]:
        return list(
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

    def _skipped_fold(
        self,
        plan: WalkForwardFoldPlan,
        feature_keys: list[str],
        skipped_reason: str,
    ) -> WalkForwardFoldResult:
        return WalkForwardFoldResult(
            fold_index=plan.fold_index,
            train_start_date=plan.train_start_date,
            train_end_date=plan.train_end_date,
            validation_start_date=plan.validation_start_date,
            validation_end_date=plan.validation_end_date,
            train_row_count=plan.train_row_count,
            validation_row_count=plan.validation_row_count,
            positive_rows=0,
            negative_rows=0,
            feature_keys=feature_keys,
            metrics={},
            skipped_reason=skipped_reason,
        )

    def _build_aggregate_metrics(
        self,
        results: list[WalkForwardFoldResult],
        y_true: list[int],
        y_pred: list[int],
        y_proba: list[float],
    ) -> WalkForwardAggregateMetrics:
        folds_completed = sum(1 for result in results if result.skipped_reason is None)
        folds_skipped = len(results) - folds_completed
        if not y_true:
            return WalkForwardAggregateMetrics(
                folds_attempted=len(results),
                folds_completed=folds_completed,
                folds_skipped=folds_skipped,
                rows_validated=0,
            )

        metrics = WalkForwardAggregateMetrics(
            folds_attempted=len(results),
            folds_completed=folds_completed,
            folds_skipped=folds_skipped,
            rows_validated=len(y_true),
            accuracy=float(accuracy_score(y_true, y_pred)),
            precision=float(precision_score(y_true, y_pred, zero_division=0)),
            recall=float(recall_score(y_true, y_pred, zero_division=0)),
            validation_positive_rate=float(np.mean(np.asarray(y_true, dtype=float))),
        )
        if len(set(y_true)) >= 2:
            metrics.roc_auc = float(roc_auc_score(y_true, y_proba))
        return metrics

    def _build_validation_version(
        self,
        *,
        dataset_version: str,
        strategy_name: str,
        feature_keys: list[str],
    ) -> str:
        payload = {
            "config": asdict(self._config),
            "dataset_version": dataset_version,
            "feature_keys": feature_keys,
            "hyperparameters": asdict(self._hyperparameters),
            "model_family": self.MODEL_FAMILY,
            "strategy_name": strategy_name,
        }
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]
        return f"{self._config.validation_version_prefix}_{digest}"
