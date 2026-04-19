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
from app.services.historical.historical_ml_scoring_schemas import (
    HistoricalMLScoringConfig,
    HistoricalMLScoringSummary,
    MLScoreExplanationRecord,
    MLScoredCandidateRecord,
    MLScoringCandidateInput,
)


class HistoricalMLScoringService:
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

    def score_candidates(
        self,
        *,
        dataset_version: str,
        strategy_name: str,
        candidates: list[MLScoringCandidateInput],
        artifact_path: str | Path,
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
        feature_baselines = self._build_feature_baselines(training_rows=training_rows, feature_keys=feature_keys)

        scored_rows: list[MLScoredCandidateRecord] = []
        skipped_rows: list[MLScoredCandidateRecord] = []
        for candidate in candidates:
            skipped_reason = self._resolve_skip_reason(
                candidate=candidate,
                strategy_name=strategy_name,
                feature_keys=feature_keys,
            )
            if skipped_reason is not None:
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
                        metadata=dict(candidate.metadata),
                    )
                )
                continue

            feature_vector = np.asarray(
                [[float(candidate.feature_values[key]) for key in feature_keys]],
                dtype=float,
            )
            probability = float(model.predict_proba(feature_vector)[0][1])
            confidence = float(abs(probability - 0.5) * 2.0)
            combined_score = (
                float(candidate.base_score) * self._config.base_score_weight
                + probability * self._config.ml_score_weight
            )
            explanation = self._build_explanation(
                candidate=candidate,
                feature_keys=feature_keys,
                feature_baselines=feature_baselines,
                feature_importances=np.asarray(model.feature_importances_, dtype=float),
            )
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
                    explanation=explanation,
                    metadata=dict(candidate.metadata),
                )
            )

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
            values = [float(row.feature_values_json[key]) for row in training_rows if row.feature_values_json.get(key) is not None]
            baselines[key] = float(np.mean(values)) if values else 0.0
        return baselines

    def _build_explanation(
        self,
        *,
        candidate: MLScoringCandidateInput,
        feature_keys: list[str],
        feature_baselines: dict[str, float],
        feature_importances: np.ndarray,
    ) -> list[MLScoreExplanationRecord]:
        records: list[MLScoreExplanationRecord] = []
        for index, feature_key in enumerate(feature_keys):
            feature_value = float(candidate.feature_values[feature_key])
            baseline_value = float(feature_baselines.get(feature_key, 0.0))
            importance_weight = float(feature_importances[index])
            signed_contribution = float((feature_value - baseline_value) * importance_weight)
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
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]
        return f"{self._config.scoring_version_prefix}_{digest}"
