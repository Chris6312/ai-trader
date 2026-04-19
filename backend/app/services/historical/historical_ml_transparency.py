from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import gettempdir
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai_research import TrainingDatasetRow
from app.services.historical.historical_ml_bundle_inspector import HistoricalMLBundleInspector
from app.services.historical.historical_ml_scoring_schemas import MLScoringCandidateInput

if TYPE_CHECKING:
    from app.services.historical.historical_ml_scoring import HistoricalMLScoringService


@dataclass(slots=True)
class TransparencyModelRecord:
    bundle_version: str
    bundle_name: str
    model_version: str
    model_family: str
    dataset_version: str
    strategy_name: str
    label_key: str
    feature_count: int
    manifest_path: str
    created_at: str | None = None
    validation_version: str | None = None
    drift_report_version: str | None = None
    scoring_version: str | None = None
    verified_artifact: bool = False


@dataclass(slots=True)
class TransparencyFeatureRecord:
    feature_key: str
    tree_importance: float | None = None
    permutation_importance: float | None = None
    standardized_mean_shift: float | None = None
    population_stability_index: float | None = None
    drift_flagged: bool = False
    direction: str | None = None
    contribution: float | None = None
    feature_value: float | None = None
    baseline_value: float | None = None


@dataclass(slots=True)
class TransparencyRowReference:
    row_key: str
    symbol: str
    asset_class: str
    timeframe: str
    decision_date: str
    entry_candle_time: str
    strategy_name: str


@dataclass(slots=True)
class TransparencyOverview:
    model: TransparencyModelRecord
    lineage: dict[str, object]
    training_metrics: dict[str, float] = field(default_factory=dict)
    global_feature_importance: list[TransparencyFeatureRecord] = field(default_factory=list)
    regime_feature_importance: list[TransparencyFeatureRecord] = field(default_factory=list)
    drift_signals: list[TransparencyFeatureRecord] = field(default_factory=list)
    health: dict[str, object] = field(default_factory=dict)
    sample_rows: list[TransparencyRowReference] = field(default_factory=list)


@dataclass(slots=True)
class TransparencyExplanation:
    bundle_version: str
    model_version: str
    dataset_version: str
    strategy_name: str
    row: TransparencyRowReference
    score: float | None
    probability: float | None
    confidence: float | None
    baseline_expectation: dict[str, float] = field(default_factory=dict)
    positive_contributors: list[TransparencyFeatureRecord] = field(default_factory=list)
    negative_contributors: list[TransparencyFeatureRecord] = field(default_factory=list)
    feature_snapshot: dict[str, object] = field(default_factory=dict)
    skipped_reason: str | None = None


class HistoricalMLTransparencyService:
    def __init__(
        self,
        session: Session,
        *,
        bundle_dir: str | Path | None = None,
    ) -> None:
        self._session = session
        self._bundle_dir = Path(
            bundle_dir or Path(gettempdir()) / "ai_trader_ml_artifacts" / "_persisted_model_bundles"
        )
        self._bundle_dir.mkdir(parents=True, exist_ok=True)
        self._bundle_inspector = HistoricalMLBundleInspector()

    def list_models(self) -> list[TransparencyModelRecord]:
        records: list[TransparencyModelRecord] = []
        for manifest_path in sorted(self._bundle_dir.glob("*/manifest.json")):
            manifest = self._bundle_inspector.load_manifest(manifest_path)
            records.append(self._build_model_record(manifest_path=manifest_path, manifest=manifest))
        records.sort(key=lambda item: (item.bundle_version, item.model_version), reverse=True)
        return records

    def get_overview(self, *, bundle_version: str, row_limit: int = 8) -> TransparencyOverview:
        manifest_path, manifest = self._load_manifest(bundle_version)
        model = self._build_model_record(manifest_path=manifest_path, manifest=manifest)
        drift_payload = self._load_optional_json_artifact(manifest, "feature_drift_review")

        global_feature_importance = [
            TransparencyFeatureRecord(
                feature_key=str(item["feature_key"]),
                tree_importance=self._optional_float(item.get("tree_importance")),
                permutation_importance=self._optional_float(item.get("permutation_importance")),
            )
            for item in cast(list[dict[str, object]], drift_payload.get("global_feature_importance", []))[:10]
        ]
        regime_feature_importance = [
            TransparencyFeatureRecord(
                feature_key=str(item["feature_key"]),
                tree_importance=self._optional_float(item.get("tree_importance")),
                permutation_importance=self._optional_float(item.get("permutation_importance")),
            )
            for item in cast(list[dict[str, object]], drift_payload.get("regime_feature_importance", []))[:10]
        ]
        drift_signals = [
            TransparencyFeatureRecord(
                feature_key=str(item["feature_key"]),
                standardized_mean_shift=self._optional_float(item.get("standardized_mean_shift")),
                population_stability_index=self._optional_float(item.get("population_stability_index")),
                drift_flagged=bool(item.get("drift_flagged", False)),
            )
            for item in cast(list[dict[str, object]], drift_payload.get("global_drift_metrics", []))[:10]
        ]

        sample_rows = self.list_historical_rows(bundle_version=bundle_version, limit=row_limit)
        training_summary = cast(dict[str, object], manifest.get("training_summary", {}))
        lineage = cast(dict[str, object], manifest.get("dataset", {})).copy()
        health = {
            "walkforward_validation_version": model.validation_version,
            "drift_report_version": model.drift_report_version,
            "scoring_version": model.scoring_version,
            "calibration_available": False,
            "confusion_matrix_available": False,
            "score_bucket_returns_available": False,
            "drift_flagged_feature_count": sum(1 for item in drift_signals if item.drift_flagged),
        }
        training_metrics = {
            str(key): float(value)
            for key, value in cast(dict[str, object], training_summary.get("metrics", {})).items()
            if isinstance(value, int | float)
        }
        return TransparencyOverview(
            model=model,
            lineage=lineage,
            training_metrics=training_metrics,
            global_feature_importance=global_feature_importance,
            regime_feature_importance=regime_feature_importance,
            drift_signals=drift_signals,
            health=health,
            sample_rows=sample_rows,
        )

    def list_historical_rows(self, *, bundle_version: str, limit: int = 25) -> list[TransparencyRowReference]:
        _, manifest = self._load_manifest(bundle_version)
        dataset_version = str(cast(dict[str, object], manifest.get("dataset", {})).get("dataset_version", ""))
        strategy_name = str(cast(dict[str, object], manifest.get("training_summary", {})).get("strategy_name", ""))
        rows = list(
            self._session.scalars(
                select(TrainingDatasetRow)
                .where(
                    TrainingDatasetRow.dataset_version == dataset_version,
                    TrainingDatasetRow.strategy_name == strategy_name,
                )
                .order_by(
                    TrainingDatasetRow.decision_date.desc(),
                    TrainingDatasetRow.symbol.asc(),
                    TrainingDatasetRow.entry_candle_time.desc(),
                )
                .limit(limit)
            )
        )
        return [self._build_row_reference(row) for row in rows]

    def explain_historical_row(self, *, bundle_version: str, row_key: str) -> TransparencyExplanation:
        _, manifest = self._load_manifest(bundle_version)
        dataset_version = str(cast(dict[str, object], manifest.get("dataset", {})).get("dataset_version", ""))
        training_summary = cast(dict[str, object], manifest.get("training_summary", {}))
        strategy_name = str(training_summary.get("strategy_name", ""))
        model_version = str(training_summary.get("model_version", ""))

        row = self._session.scalar(
            select(TrainingDatasetRow).where(
                TrainingDatasetRow.dataset_version == dataset_version,
                TrainingDatasetRow.row_key == row_key,
            )
        )
        if row is None:
            raise ValueError(f"unknown row_key for bundle {bundle_version}: {row_key}")

        artifact_status = self._bundle_inspector.resolve_model_artifact_status(manifest=manifest, manifest_path=self._bundle_dir / bundle_version / "manifest.json", allow_missing=False)
        artifact_path = artifact_status.artifact_path
        if artifact_path is None or not artifact_status.verified_artifact:
            raise ValueError(f"persisted model artifact missing for bundle: {bundle_version}")

        # Lazy import to avoid pulling optional ML dependencies like joblib/sklearn
        # into backend startup paths that only need the API layer to boot.
        from app.services.historical.historical_ml_scoring import HistoricalMLScoringService

        scoring_service = HistoricalMLScoringService(self._session)
        candidate = MLScoringCandidateInput(
            symbol=row.symbol,
            asset_class=row.asset_class.value,
            timeframe=row.timeframe,
            candle_time=row.entry_candle_time,
            source_label=row.source_label,
            strategy_name=row.strategy_name,
            base_rank=1,
            base_score=self._resolve_base_score(row),
            feature_values={
                str(key): float(value)
                for key, value in row.feature_values_json.items()
                if isinstance(value, int | float)
            },
            metadata={"row_key": row.row_key},
        )
        scoring_summary = scoring_service.score_candidates(
            dataset_version=dataset_version,
            strategy_name=strategy_name,
            candidates=[candidate],
            artifact_path=artifact_path,
        )
        candidate_result = scoring_summary.candidates[0]

        positive: list[TransparencyFeatureRecord] = []
        negative: list[TransparencyFeatureRecord] = []
        baseline_expectation: dict[str, float] = {}
        for item in candidate_result.explanation:
            record = TransparencyFeatureRecord(
                feature_key=item.feature_key,
                contribution=item.signed_contribution,
                direction="positive" if item.signed_contribution >= 0 else "negative",
                feature_value=item.feature_value,
                baseline_value=item.baseline_value,
            )
            baseline_expectation[item.feature_key] = item.baseline_value
            if item.signed_contribution >= 0:
                positive.append(record)
            else:
                negative.append(record)

        positive.sort(key=lambda entry: (entry.contribution or 0.0), reverse=True)
        negative.sort(key=lambda entry: (entry.contribution or 0.0))

        return TransparencyExplanation(
            bundle_version=bundle_version,
            model_version=model_version,
            dataset_version=dataset_version,
            strategy_name=strategy_name,
            row=self._build_row_reference(row),
            score=candidate_result.combined_score,
            probability=candidate_result.ml_probability,
            confidence=candidate_result.ml_confidence,
            baseline_expectation=baseline_expectation,
            positive_contributors=positive[:5],
            negative_contributors=negative[:5],
            feature_snapshot=row.feature_values_json,
            skipped_reason=candidate_result.scoring_skipped_reason,
        )

    def _load_manifest(self, bundle_version: str) -> tuple[Path, dict[str, object]]:
        manifest_path = self._bundle_dir / bundle_version / "manifest.json"
        if not manifest_path.exists():
            raise ValueError(f"unknown bundle_version: {bundle_version}")
        return manifest_path, self._bundle_inspector.load_manifest(manifest_path)

    def _build_model_record(self, *, manifest_path: Path, manifest: dict[str, object]) -> TransparencyModelRecord:
        training_summary = cast(dict[str, object], manifest.get("training_summary", {}))
        references = cast(list[dict[str, object]], manifest.get("references", []))
        validation_ref = self._find_reference(references, "walkforward_validation")
        drift_ref = self._find_reference(references, "feature_drift_review")
        scoring_ref = self._find_reference(references, "scoring_profile")
        artifact_status = self._bundle_inspector.resolve_model_artifact_status(manifest=manifest, manifest_path=manifest_path, allow_missing=True)
        return TransparencyModelRecord(
            bundle_version=str(manifest.get("bundle_version", manifest_path.parent.name)),
            bundle_name=str(manifest.get("bundle_name", "baseline_model_bundle")),
            model_version=str(training_summary.get("model_version", "")),
            model_family=str(training_summary.get("model_family", "")),
            dataset_version=str(cast(dict[str, object], manifest.get("dataset", {})).get("dataset_version", "")),
            strategy_name=str(training_summary.get("strategy_name", "")),
            label_key=str(training_summary.get("label_key", "")),
            feature_count=len(cast(list[object], training_summary.get("feature_keys", []))),
            manifest_path=str(manifest_path),
            created_at=self._optional_str(training_summary.get("trained_at")),
            validation_version=validation_ref,
            drift_report_version=drift_ref,
            scoring_version=scoring_ref,
            verified_artifact=artifact_status.verified_artifact,
        )

    def _load_optional_json_artifact(self, manifest: dict[str, object], reference_type: str) -> dict[str, object]:
        references = cast(list[dict[str, object]], manifest.get("references", []))
        for reference in references:
            if reference.get("reference_type") != reference_type:
                continue
            artifact_path = reference.get("artifact_path")
            if artifact_path is None:
                continue
            path = Path(str(artifact_path))
            if not path.exists():
                continue
            return self._read_json(path)
        return {}

    @staticmethod
    def _find_reference(references: list[dict[str, object]], reference_type: str) -> str | None:
        for reference in references:
            if reference.get("reference_type") == reference_type:
                value = reference.get("reference_version")
                return str(value) if value is not None else None
        return None

    @staticmethod
    def _resolve_base_score(row: TrainingDatasetRow) -> float:
        value = row.metadata_json.get("base_score")
        if isinstance(value, int | float):
            return float(value)
        for key in ("technical_score", "universe_score", "score"):
            other = row.metadata_json.get(key)
            if isinstance(other, int | float):
                return float(other)
        return 0.5

    @staticmethod
    def _build_row_reference(row: TrainingDatasetRow) -> TransparencyRowReference:
        return TransparencyRowReference(
            row_key=row.row_key,
            symbol=row.symbol,
            asset_class=row.asset_class.value,
            timeframe=row.timeframe,
            decision_date=row.decision_date.isoformat(),
            entry_candle_time=row.entry_candle_time.isoformat(),
            strategy_name=row.strategy_name,
        )

    @staticmethod
    def _read_json(path: Path) -> dict[str, object]:
        return cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))

    @staticmethod
    def _optional_str(value: object) -> str | None:
        return str(value) if value is not None else None

    @staticmethod
    def _optional_float(value: object) -> float | None:
        if isinstance(value, int | float):
            return float(value)
        return None