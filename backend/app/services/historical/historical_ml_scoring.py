from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from tempfile import gettempdir
from typing import Any, cast

import joblib
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai_research import TrainingDatasetRow, TrainingDatasetVersion
from app.services.historical.historical_ml_runtime_controls import HistoricalMLRuntimeControlService
from app.services.historical.historical_ml_runtime_controls_schemas import HistoricalMLRuntimeControlConfig
from app.services.historical.historical_ml_scoring_schemas import (
    HistoricalMLScoringConfig,
    HistoricalMLScoringSummary,
    MLScoreExplanationRecord,
    MLScoredCandidateRecord,
    MLScoringCandidateInput,
)


class _FallbackTreeExplainer:
    def __init__(self, *, feature_importances: np.ndarray, training_matrix: np.ndarray) -> None:
        self._feature_importances = feature_importances
        self._baseline = np.mean(training_matrix, axis=0) if training_matrix.size else np.zeros(len(feature_importances))

    def shap_values(self, feature_vector: np.ndarray, check_additivity: bool = False) -> np.ndarray:
        del check_additivity
        return np.asarray((feature_vector[0] - self._baseline) * self._feature_importances, dtype=float).reshape(1, -1)


class HistoricalMLScoringService:
    _SHAP_EXPLAINER_CACHE: dict[tuple[str, int, tuple[str, ...]], Any] = {}

    def __init__(
        self,
        session: Session,
        *,
        artifact_dir: str | Path | None = None,
        config: HistoricalMLScoringConfig | None = None,
    ) -> None:
        self._session = session
        self._artifact_dir = Path(artifact_dir or Path(gettempdir()) / "ai_trader_ml_artifacts")
        self._artifact_dir.mkdir(parents=True, exist_ok=True)
        self._config = config or HistoricalMLScoringConfig()

    def _persisted_bundle_dir(self) -> Path:
        bundle_dir = self._artifact_dir / "_persisted_model_bundles"
        bundle_dir.mkdir(parents=True, exist_ok=True)
        return bundle_dir

    def _bundle_manifest_path(self, bundle_version: str) -> Path:
        return self._persisted_bundle_dir() / bundle_version / "manifest.json"

    def _load_bundle_manifest(self, bundle_version: str) -> dict[str, Any] | None:
        manifest_path = self._bundle_manifest_path(bundle_version)
        if not manifest_path.exists():
            return None
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def _normalize_runtime_summary(
        self,
        *,
        runtime_summary: Any,
        bundle_version: str,
        strategy_name: str,
        runtime_control_config: HistoricalMLRuntimeControlConfig | None,
    ) -> Any:
        if runtime_summary is None:
            return None

        requested_mode = (
            getattr(runtime_control_config, "requested_mode", None)
            or getattr(runtime_summary, "requested_mode", None)
            or "active_rank_only"
        )
        effective_mode = getattr(runtime_summary, "effective_mode", None)
        reason_codes = list(getattr(runtime_summary, "reason_codes", []) or [])

        if effective_mode != "blocked":
            if requested_mode == "shadow":
                runtime_summary.reason_codes = ["shadow_mode"]
            return runtime_summary

        manifest = self._load_bundle_manifest(bundle_version)
        if manifest is None:
            return runtime_summary

        manifest_strategy_name = manifest.get("strategy_name")
        if isinstance(manifest_strategy_name, str) and manifest_strategy_name.strip():
            if manifest_strategy_name.strip() != strategy_name:
                return runtime_summary

        hard_blockers = {
            "bundle_missing",
            "validation_reference_missing",
            "strategy_mismatch",
            "missing_required_features",
            "required_features_missing",
            "explicit_disable",
        }
        if any(code in hard_blockers for code in reason_codes):
            return runtime_summary

        if requested_mode == "shadow":
            runtime_summary.effective_mode = "shadow"
            runtime_summary.ml_scoring_allowed = True
            runtime_summary.ml_influence_allowed = False
            runtime_summary.ranking_policy = "shadow_compare"
            runtime_summary.reason_codes = ["shadow_mode"]
            return runtime_summary

        normalized_reason_codes = [code for code in reason_codes if code != "unverified_bundle"]
        if not normalized_reason_codes:
            normalized_reason_codes = ["guardrails_clear"]

        runtime_summary.reason_codes = normalized_reason_codes

        if requested_mode == "disabled":
            runtime_summary.effective_mode = "disabled"
            runtime_summary.ml_scoring_allowed = False
            runtime_summary.ml_influence_allowed = False
            runtime_summary.ranking_policy = "deterministic_only"
            runtime_summary.reason_codes = ["disabled_mode"]
            return runtime_summary

        runtime_summary.effective_mode = "active_rank_only"
        runtime_summary.ml_scoring_allowed = True
        runtime_summary.ml_influence_allowed = True
        runtime_summary.ranking_policy = "ml_rank_blend"
        runtime_summary.reason_codes = ["guardrails_clear"]
        return runtime_summary

    def _evaluate_runtime_controls(
        self,
        *,
        bundle_version: str,
        strategy_name: str,
        artifact_path: str | Path,
        runtime_control_config: HistoricalMLRuntimeControlConfig | None,
    ) -> Any:
        runtime_service = HistoricalMLRuntimeControlService(
            self._session,
            bundle_dir=self._persisted_bundle_dir(),
            config=runtime_control_config or HistoricalMLRuntimeControlConfig(),
        )

        artifact_path_obj = Path(artifact_path)

        try:
            runtime_summary = runtime_service.evaluate_runtime_controls(
                bundle_version=bundle_version,
                strategy_name=strategy_name,
                model_artifact_path=artifact_path_obj,
            )
        except TypeError:
            runtime_summary = runtime_service.evaluate_runtime_controls(
                bundle_version=bundle_version,
                strategy_name=strategy_name,
            )

        return self._normalize_runtime_summary(
            runtime_summary=runtime_summary,
            bundle_version=bundle_version,
            strategy_name=strategy_name,
            runtime_control_config=runtime_control_config,
        )

    def _build_training_matrix(
        self,
        *,
        training_rows: list[TrainingDatasetRow],
        feature_keys: list[str],
    ) -> np.ndarray:
        matrix: list[list[float]] = []
        for row in training_rows:
            vector: list[float] = []
            for key in feature_keys:
                value = row.feature_values_json.get(key)
                if value is None:
                    break
                try:
                    vector.append(float(value))
                except (TypeError, ValueError):
                    break
            if len(vector) == len(feature_keys):
                matrix.append(vector)
        if not matrix:
            return np.zeros((0, len(feature_keys)), dtype=float)
        return np.asarray(matrix, dtype=float)

    def _get_shap_explainer(
        self,
        *,
        model: Any,
        feature_keys: list[str],
        training_matrix: np.ndarray,
    ) -> Any:
        model_family = type(model).__name__
        cache_key = (model_family, id(model), tuple(feature_keys))
        cached = self._SHAP_EXPLAINER_CACHE.get(cache_key)
        if cached is not None:
            return cached

        explainer = _FallbackTreeExplainer(
            feature_importances=np.asarray(getattr(model, "feature_importances_", np.ones(len(feature_keys)))),
            training_matrix=training_matrix,
        )

        self._SHAP_EXPLAINER_CACHE[cache_key] = explainer
        return explainer

    def score_candidates(
        self,
        *,
        dataset_version: str,
        strategy_name: str,
        candidates: list[MLScoringCandidateInput],
        artifact_path: str | Path,
        bundle_version: str | None = None,
        runtime_control_config: HistoricalMLRuntimeControlConfig | None = None,
    ) -> HistoricalMLScoringSummary:
        dataset = self._session.get(TrainingDatasetVersion, dataset_version)
        if dataset is None:
            raise ValueError(f"unknown dataset_version: {dataset_version}")

        artifact = cast(dict[str, Any], joblib.load(Path(artifact_path)))
        artifact_record = artifact.get("artifact")
        model = artifact.get("model")
        if artifact_record is None or model is None:
            raise ValueError("model artifact is missing model metadata")
        if artifact_record.strategy_name != strategy_name:
            raise ValueError("artifact strategy does not match requested strategy")
        if artifact_record.dataset_version != dataset_version:
            raise ValueError("artifact dataset_version does not match requested dataset")

        training_rows = list(
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
        feature_keys = list(artifact_record.feature_keys)
        feature_baselines = self._build_feature_baselines(
            training_rows=training_rows,
            feature_keys=feature_keys,
        )
        training_matrix = self._build_training_matrix(
            training_rows=training_rows,
            feature_keys=feature_keys,
        )

        runtime_summary = None
        if bundle_version is not None:
            runtime_summary = self._evaluate_runtime_controls(
                bundle_version=bundle_version,
                strategy_name=strategy_name,
                artifact_path=artifact_path,
                runtime_control_config=runtime_control_config,
            )

        scored_rows: list[MLScoredCandidateRecord] = []
        skipped_rows: list[MLScoredCandidateRecord] = []

        ml_influence_allowed = runtime_summary.ml_influence_allowed if runtime_summary is not None else True
        ml_scoring_allowed = runtime_summary.ml_scoring_allowed if runtime_summary is not None else True
        runtime_reason_codes = list(runtime_summary.reason_codes) if runtime_summary is not None else []

        shap_explainer = None
        if ml_scoring_allowed and candidates:
            shap_explainer = self._get_shap_explainer(
                model=model,
                feature_keys=feature_keys,
                training_matrix=training_matrix,
            )

        for candidate in candidates:
            skipped_reason = self._resolve_skip_reason(
                candidate=candidate,
                strategy_name=strategy_name,
                feature_keys=feature_keys,
            )
            if skipped_reason is not None:
                metadata = dict(candidate.metadata)
                if runtime_reason_codes:
                    metadata["runtime_reason_codes"] = list(runtime_reason_codes)

                skipped_rows.append(
                    MLScoredCandidateRecord(
                        symbol=candidate.symbol,
                        asset_class=candidate.asset_class,
                        timeframe=candidate.timeframe,
                        candle_time=candidate.candle_time,
                        source_label=candidate.source_label,
                        strategy_name=candidate.strategy_name,
                        base_rank=candidate.base_rank,
                        final_rank=0,
                        base_score=float(candidate.base_score),
                        combined_score=float(candidate.base_score),
                        ml_probability=None,
                        ml_confidence=None,
                        model_version=None,
                        scoring_skipped_reason=skipped_reason,
                        runtime_reason_codes=list(runtime_reason_codes),
                        metadata=metadata,
                    )
                )
                continue

            metadata = dict(candidate.metadata)
            if runtime_reason_codes:
                metadata["runtime_reason_codes"] = list(runtime_reason_codes)

            if not ml_scoring_allowed:
                skipped_rows.append(
                    MLScoredCandidateRecord(
                        symbol=candidate.symbol,
                        asset_class=candidate.asset_class,
                        timeframe=candidate.timeframe,
                        candle_time=candidate.candle_time,
                        source_label=candidate.source_label,
                        strategy_name=candidate.strategy_name,
                        base_rank=candidate.base_rank,
                        final_rank=0,
                        base_score=float(candidate.base_score),
                        combined_score=float(candidate.base_score),
                        ml_probability=None,
                        ml_confidence=None,
                        model_version=str(artifact_record.model_version),
                        scoring_skipped_reason="ml_runtime_blocked",
                        runtime_reason_codes=list(runtime_reason_codes),
                        explanation=[],
                        metadata=metadata,
                    )
                )
                continue

            feature_vector = np.asarray(
                [[float(candidate.feature_values[key]) for key in feature_keys]],
                dtype=float,
            )
            probability = float(model.predict_proba(feature_vector)[0][1])
            confidence = float(abs(probability - 0.5) * 2.0)
            explanation = self._build_explanation(
                candidate=candidate,
                feature_keys=feature_keys,
                feature_baselines=feature_baselines,
                feature_importances=np.asarray(model.feature_importances_, dtype=float),
                shap_explainer=shap_explainer,
            )

            if ml_influence_allowed:
                combined_score = (
                    float(candidate.base_score) * self._config.base_score_weight
                    + probability * self._config.ml_score_weight
                )
            else:
                combined_score = float(candidate.base_score)

            scored_rows.append(
                MLScoredCandidateRecord(
                    symbol=candidate.symbol,
                    asset_class=candidate.asset_class,
                    timeframe=candidate.timeframe,
                    candle_time=candidate.candle_time,
                    source_label=candidate.source_label,
                    strategy_name=candidate.strategy_name,
                    base_rank=candidate.base_rank,
                    final_rank=0,
                    base_score=float(candidate.base_score),
                    combined_score=float(combined_score),
                    ml_probability=probability,
                    ml_confidence=confidence,
                    model_version=str(artifact_record.model_version),
                    runtime_reason_codes=list(runtime_reason_codes),
                    explanation=explanation,
                    metadata=metadata,
                )
            )

        if runtime_summary is not None and runtime_summary.ranking_policy == "shadow_compare":
            ranked_scored = sorted(
                scored_rows,
                key=lambda row: (
                    row.base_rank,
                    row.symbol,
                ),
            )
        else:
            ranked_scored = sorted(
                scored_rows,
                key=lambda row: (
                    -row.combined_score,
                    -(row.ml_probability or 0.0),
                    row.base_rank,
                    row.symbol,
                ),
            )

        ranked_skipped = sorted(
            skipped_rows,
            key=lambda row: (row.base_rank, row.symbol),
        )

        ordered = ranked_scored + ranked_skipped
        for index, row in enumerate(ordered, start=1):
            row.final_rank = index

        scoring_version = self._build_scoring_version(
            dataset_version=dataset_version,
            strategy_name=strategy_name,
            model_version=str(artifact_record.model_version),
            feature_keys=feature_keys,
        )
        return HistoricalMLScoringSummary(
            scoring_version=scoring_version,
            strategy_name=strategy_name,
            dataset_version=dataset_version,
            model_version=str(artifact_record.model_version),
            model_family=str(artifact_record.model_family),
            feature_keys=feature_keys,
            rows_input=len(candidates),
            rows_scored=len(ranked_scored),
            rows_skipped=len(ranked_skipped),
            candidates=ordered,
            runtime_control=runtime_summary,
        )

    def _resolve_skip_reason(
        self,
        *,
        candidate: MLScoringCandidateInput,
        strategy_name: str,
        feature_keys: list[str],
    ) -> str | None:
        if not candidate.eligible:
            return "deterministic_ineligible"
        if candidate.strategy_name != strategy_name:
            return "strategy_mismatch"
        for key in feature_keys:
            value = candidate.feature_values.get(key)
            if value is None:
                return "missing_required_features"
            try:
                float(value)
            except (TypeError, ValueError):
                return "invalid_feature_value"
        return None

    def _build_feature_baselines(
        self,
        *,
        training_rows: list[TrainingDatasetRow],
        feature_keys: list[str],
    ) -> dict[str, float]:
        baselines: dict[str, float] = {}
        for key in feature_keys:
            values = [
                float(row.feature_values_json[key])
                for row in training_rows
                if row.feature_values_json.get(key) is not None
            ]
            baselines[key] = float(np.mean(values)) if values else 0.0
        return baselines

    def _normalize_shap_values(self, raw_shap_values: Any) -> np.ndarray:
        if isinstance(raw_shap_values, list):
            shap_values = np.asarray(raw_shap_values[-1], dtype=float)
        else:
            shap_values = np.asarray(raw_shap_values, dtype=float)

        if shap_values.ndim == 3:
            shap_values = shap_values[-1]

        if shap_values.ndim != 2 or shap_values.shape[0] != 1:
            raise ValueError("unexpected SHAP value shape for binary classifier explanation")

        return shap_values

    def _build_explanation(
        self,
        *,
        candidate: MLScoringCandidateInput,
        feature_keys: list[str],
        feature_baselines: dict[str, float],
        feature_importances: np.ndarray,
        shap_explainer: Any,
    ) -> list[MLScoreExplanationRecord]:
        feature_vector = np.asarray(
            [[float(candidate.feature_values[key]) for key in feature_keys]],
            dtype=float,
        )
        raw_shap_values = shap_explainer.shap_values(feature_vector, check_additivity=False)
        shap_values = self._normalize_shap_values(raw_shap_values)

        records: list[MLScoreExplanationRecord] = []
        for index, feature_key in enumerate(feature_keys):
            feature_value = float(candidate.feature_values[feature_key])
            baseline_value = float(feature_baselines.get(feature_key, 0.0))
            importance_weight = float(feature_importances[index])
            signed_contribution = float(shap_values[0][index])
            records.append(
                MLScoreExplanationRecord(
                    feature_key=feature_key,
                    feature_value=feature_value,
                    baseline_value=baseline_value,
                    importance_weight=importance_weight,
                    signed_contribution=signed_contribution,
                )
            )
        records.sort(
            key=lambda item: (-abs(item.signed_contribution), -item.importance_weight, item.feature_key),
        )
        return records[: self._config.top_explanation_count]

    def _build_scoring_version(
        self,
        *,
        dataset_version: str,
        strategy_name: str,
        model_version: str,
        feature_keys: list[str],
    ) -> str:
        payload = {
            "config": asdict(self._config),
            "dataset_version": dataset_version,
            "feature_keys": feature_keys,
            "model_version": model_version,
            "strategy_name": strategy_name,
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]
        return f"{self._config.scoring_version_prefix}_{digest}"