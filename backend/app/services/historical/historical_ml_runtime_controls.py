from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from tempfile import gettempdir
from typing import Any

from sqlalchemy.orm import Session

from app.services.historical.historical_ml_runtime_controls_schemas import (
    HistoricalMLRuntimeControlConfig,
    HistoricalMLRuntimeControlSummary,
)


class HistoricalMLRuntimeControlService:
    def __init__(
        self,
        session: Session,
        *,
        bundle_dir: str | Path | None = None,
        config: HistoricalMLRuntimeControlConfig | None = None,
    ) -> None:
        self._session = session
        self._bundle_dir = Path(
            bundle_dir or Path(gettempdir()) / "ai_trader_ml_artifacts" / "_persisted_model_bundles"
        )
        self._bundle_dir.mkdir(parents=True, exist_ok=True)
        self._config = config or HistoricalMLRuntimeControlConfig()

    def evaluate_runtime_controls(
        self,
        *,
        bundle_version: str,
        strategy_name: str,
        as_of: datetime | None = None,
    ) -> HistoricalMLRuntimeControlSummary:
        evaluated_at = as_of.astimezone(UTC) if as_of is not None else datetime.now(UTC)
        reason_codes: list[str] = []
        missing_feature_keys: list[str] = []
        metadata: dict[str, object] = {}

        if self._config.requested_mode == "disabled":
            return HistoricalMLRuntimeControlSummary(
                bundle_version=bundle_version,
                strategy_name=strategy_name,
                requested_mode=self._config.requested_mode,
                effective_mode="disabled",
                ranking_policy="deterministic_only",
                ml_scoring_allowed=False,
                ml_influence_allowed=False,
                deterministic_fallback_active=True,
                verified_artifact=False,
                validation_reference_present=False,
                stale_after_days=self._config.stale_after_days,
                validation_metric_key=self._config.validation_metric_key,
                evaluated_at=evaluated_at,
                reason_codes=["operator_disabled"],
            )

        manifest_path = self._bundle_dir / bundle_version / "manifest.json"
        if not manifest_path.exists():
            return HistoricalMLRuntimeControlSummary(
                bundle_version=bundle_version,
                strategy_name=strategy_name,
                requested_mode=self._config.requested_mode,
                effective_mode="blocked",
                ranking_policy="deterministic_only",
                ml_scoring_allowed=False,
                ml_influence_allowed=False,
                deterministic_fallback_active=True,
                verified_artifact=False,
                validation_reference_present=False,
                stale_after_days=self._config.stale_after_days,
                validation_metric_key=self._config.validation_metric_key,
                evaluated_at=evaluated_at,
                reason_codes=["bundle_not_found"],
            )

        manifest = self._read_json(manifest_path)
        metadata["bundle_name"] = str(manifest.get("bundle_name") or "")
        metadata["dataset_version"] = str((manifest.get("dataset") or {}).get("dataset_version") or "")

        manifest_strategy_name = str((manifest.get("training_summary") or {}).get("strategy_name") or "")
        if manifest_strategy_name and manifest_strategy_name != strategy_name:
            reason_codes.append("strategy_mismatch")
            metadata["manifest_strategy_name"] = manifest_strategy_name

        feature_keys = [str(item) for item in (manifest.get("dataset") or {}).get("feature_keys") or []]
        if self._config.required_feature_keys:
            missing_feature_keys = [key for key in self._config.required_feature_keys if key not in feature_keys]
            if missing_feature_keys:
                reason_codes.append("missing_required_features")

        artifact_path = self._resolve_artifact_path(manifest=manifest, manifest_path=manifest_path)
        verified_artifact = artifact_path is not None and artifact_path.exists()
        if self._config.require_verified_bundle and not verified_artifact:
            reason_codes.append("unverified_bundle")

        validation_reference_present = self._has_reference(manifest=manifest, reference_type="walkforward_validation")
        if self._config.require_validation_reference and not validation_reference_present:
            reason_codes.append("validation_reference_missing")

        validation_metric_value = self._resolve_validation_metric(manifest=manifest)
        if self._config.minimum_validation_metric is not None:
            if validation_metric_value is None:
                reason_codes.append("validation_metric_missing")
            elif validation_metric_value < self._config.minimum_validation_metric:
                reason_codes.append("validation_threshold_failed")

        bundle_age_days = self._resolve_bundle_age_days(manifest=manifest, evaluated_at=evaluated_at)
        if bundle_age_days is not None and bundle_age_days > self._config.stale_after_days:
            reason_codes.append("bundle_stale")

        if reason_codes:
            return HistoricalMLRuntimeControlSummary(
                bundle_version=bundle_version,
                strategy_name=strategy_name,
                requested_mode=self._config.requested_mode,
                effective_mode="blocked",
                ranking_policy="deterministic_only",
                ml_scoring_allowed=False,
                ml_influence_allowed=False,
                deterministic_fallback_active=True,
                verified_artifact=verified_artifact,
                validation_reference_present=validation_reference_present,
                bundle_age_days=bundle_age_days,
                stale_after_days=self._config.stale_after_days,
                validation_metric_key=self._config.validation_metric_key,
                validation_metric_value=validation_metric_value,
                evaluated_at=evaluated_at,
                reason_codes=reason_codes,
                missing_feature_keys=missing_feature_keys,
                metadata=metadata,
            )

        effective_mode = "shadow" if self._config.requested_mode == "shadow" else "active_rank_only"
        ranking_policy = "shadow_compare" if effective_mode == "shadow" else "ml_rank_only"
        return HistoricalMLRuntimeControlSummary(
            bundle_version=bundle_version,
            strategy_name=strategy_name,
            requested_mode=self._config.requested_mode,
            effective_mode=effective_mode,
            ranking_policy=ranking_policy,
            ml_scoring_allowed=True,
            ml_influence_allowed=effective_mode == "active_rank_only",
            deterministic_fallback_active=effective_mode != "active_rank_only",
            verified_artifact=verified_artifact,
            validation_reference_present=validation_reference_present,
            bundle_age_days=bundle_age_days,
            stale_after_days=self._config.stale_after_days,
            validation_metric_key=self._config.validation_metric_key,
            validation_metric_value=validation_metric_value,
            evaluated_at=evaluated_at,
            reason_codes=["shadow_mode"] if effective_mode == "shadow" else [],
            metadata=metadata,
        )

    def _resolve_artifact_path(self, *, manifest: dict[str, Any], manifest_path: Path) -> Path | None:
        training_summary = manifest.get("training_summary") or {}
        training_artifact_path = training_summary.get("artifact_path")
        if isinstance(training_artifact_path, str) and training_artifact_path:
            return Path(training_artifact_path)

        for reference in manifest.get("references") or []:
            if str(reference.get("reference_type") or "") != "model_training":
                continue
            artifact_path = reference.get("artifact_path")
            if isinstance(artifact_path, str) and artifact_path:
                return Path(artifact_path)

        bundle_local_artifact = manifest_path.parent / "model_artifact.joblib"
        if bundle_local_artifact.exists():
            return bundle_local_artifact
        return None

    def _has_reference(self, *, manifest: dict[str, Any], reference_type: str) -> bool:
        for reference in manifest.get("references") or []:
            if str(reference.get("reference_type") or "") == reference_type:
                return True
        return False

    def _resolve_validation_metric(self, *, manifest: dict[str, Any]) -> float | None:
        validation_summary = manifest.get("validation_summary") or {}
        aggregate_metrics = validation_summary.get("aggregate_metrics") or {}
        if self._config.validation_metric_key in aggregate_metrics:
            return self._optional_float(aggregate_metrics.get(self._config.validation_metric_key))
        return None

    def _resolve_bundle_age_days(self, *, manifest: dict[str, Any], evaluated_at: datetime) -> int | None:
        training_summary = manifest.get("training_summary") or {}
        trained_at_raw = training_summary.get("trained_at") or training_summary.get("created_at")
        trained_at = self._parse_datetime(trained_at_raw)
        if trained_at is None:
            return None
        delta = evaluated_at - trained_at.astimezone(UTC)
        return max(0, delta.days)

    def _parse_datetime(self, value: object) -> datetime | None:
        if not isinstance(value, str) or not value:
            return None
        candidate = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed

    def _optional_float(self, value: object) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _read_json(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))
