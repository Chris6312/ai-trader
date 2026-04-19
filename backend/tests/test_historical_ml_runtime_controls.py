from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory, gettempdir

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.services.historical.historical_ml_runtime_controls import HistoricalMLRuntimeControlService
from app.services.historical.historical_ml_runtime_controls_schemas import HistoricalMLRuntimeControlConfig


BUNDLE_ROOT = Path(gettempdir()) / "ai_trader_ml_artifacts" / "_persisted_model_bundles"


def _build_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def _write_manifest(
    *,
    bundle_version: str,
    strategy_name: str = "momentum",
    trained_at: str = "2026-04-10T12:00:00+00:00",
    include_artifact: bool = True,
    include_validation_reference: bool = True,
    validation_metric: float | None = 0.74,
    feature_keys: list[str] | None = None,
) -> Path:
    bundle_dir = BUNDLE_ROOT / bundle_version
    shutil.rmtree(bundle_dir, ignore_errors=True)
    bundle_dir.mkdir(parents=True, exist_ok=True)

    artifact_path = bundle_dir / "model_artifact.joblib"
    if include_artifact:
        artifact_path.write_bytes(b"placeholder")

    references: list[dict[str, object]] = [
        {
            "reference_type": "model_training",
            "reference_version": "12g_v1_model",
            "artifact_path": str(artifact_path),
        }
    ]
    if include_validation_reference:
        references.append(
            {
                "reference_type": "walkforward_validation",
                "reference_version": "12h_v1_validation",
            }
        )

    payload: dict[str, object] = {
        "bundle_name": "baseline_model_bundle",
        "bundle_version": bundle_version,
        "dataset": {
            "dataset_version": "12f_dataset_v1",
            "feature_keys": feature_keys or ["feature_alpha", "feature_beta"],
        },
        "training_summary": {
            "strategy_name": strategy_name,
            "trained_at": trained_at,
            "artifact_path": str(artifact_path),
        },
        "references": references,
    }
    if validation_metric is not None:
        payload["validation_summary"] = {
            "aggregate_metrics": {
                "roc_auc": validation_metric,
            }
        }

    manifest_path = bundle_dir / "manifest.json"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    return manifest_path


def test_runtime_controls_support_disabled_shadow_and_active_modes() -> None:
    session = _build_session()
    bundle_version = "12n_runtime_modes"
    _write_manifest(bundle_version=bundle_version)

    disabled = HistoricalMLRuntimeControlService(
        session,
        config=HistoricalMLRuntimeControlConfig(requested_mode="disabled"),
    ).evaluate_runtime_controls(bundle_version=bundle_version, strategy_name="momentum")
    assert disabled.effective_mode == "disabled"
    assert disabled.ranking_policy == "deterministic_only"
    assert disabled.reason_codes == ["operator_disabled"]

    shadow = HistoricalMLRuntimeControlService(
        session,
        config=HistoricalMLRuntimeControlConfig(requested_mode="shadow"),
    ).evaluate_runtime_controls(bundle_version=bundle_version, strategy_name="momentum")
    assert shadow.effective_mode == "shadow"
    assert shadow.ml_scoring_allowed is True
    assert shadow.ml_influence_allowed is False
    assert shadow.deterministic_fallback_active is True
    assert shadow.ranking_policy == "shadow_compare"
    assert shadow.reason_codes == ["shadow_mode"]

    active = HistoricalMLRuntimeControlService(
        session,
        config=HistoricalMLRuntimeControlConfig(requested_mode="active_rank_only"),
    ).evaluate_runtime_controls(bundle_version=bundle_version, strategy_name="momentum")
    assert active.effective_mode == "active_rank_only"
    assert active.ml_scoring_allowed is True
    assert active.ml_influence_allowed is True
    assert active.deterministic_fallback_active is False
    assert active.ranking_policy == "ml_rank_only"
    assert active.reason_codes == []


def test_runtime_controls_block_stale_unverified_and_validation_failures() -> None:
    session = _build_session()
    bundle_version = "12n_runtime_blocked"
    _write_manifest(
        bundle_version=bundle_version,
        include_artifact=False,
        include_validation_reference=False,
        validation_metric=0.41,
        trained_at="2026-03-01T12:00:00+00:00",
    )
    summary = HistoricalMLRuntimeControlService(
        session,
        config=HistoricalMLRuntimeControlConfig(
            requested_mode="active_rank_only",
            stale_after_days=7,
            minimum_validation_metric=0.60,
        ),
    ).evaluate_runtime_controls(
        bundle_version=bundle_version,
        strategy_name="momentum",
        as_of=datetime(2026, 4, 18, 12, tzinfo=UTC),
    )

    assert summary.effective_mode == "blocked"
    assert summary.ranking_policy == "deterministic_only"
    assert summary.ml_scoring_allowed is False
    assert summary.deterministic_fallback_active is True
    assert summary.bundle_age_days == 48
    assert set(summary.reason_codes) == {
        "unverified_bundle",
        "validation_reference_missing",
        "validation_threshold_failed",
        "bundle_stale",
    }


def test_runtime_controls_block_strategy_and_feature_mismatches() -> None:
    session = _build_session()
    bundle_version = "12n_runtime_feature_checks"
    _write_manifest(bundle_version=bundle_version, strategy_name="trend_continuation", feature_keys=["feature_alpha"])
    summary = HistoricalMLRuntimeControlService(
        session,
        config=HistoricalMLRuntimeControlConfig(
            requested_mode="active_rank_only",
            required_feature_keys=["feature_alpha", "feature_beta"],
        ),
    ).evaluate_runtime_controls(bundle_version=bundle_version, strategy_name="momentum")

    assert summary.effective_mode == "blocked"
    assert summary.missing_feature_keys == ["feature_beta"]
    assert set(summary.reason_codes) == {"strategy_mismatch", "missing_required_features"}
