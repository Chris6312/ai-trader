from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.ai_research import TrainingDatasetRow, TrainingDatasetVersion
from app.models.trading import AssetClass
from app.services.historical.historical_baseline_model import HistoricalBaselineModelService
from app.services.historical.historical_ml_runtime_controls_schemas import HistoricalMLRuntimeControlConfig
from app.services.historical.historical_ml_scoring import HistoricalMLScoringService
from app.services.historical.historical_ml_scoring_schemas import HistoricalMLScoringConfig, MLScoringCandidateInput


def _build_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed_dataset(session: Session) -> None:
    session.add(
        TrainingDatasetVersion(
            dataset_version="12f_dataset_v1",
            dataset_name="baseline_training_dataset",
            dataset_definition_version="12f_v1",
            asset_class=AssetClass.STOCK,
            timeframe="1h",
            source_label="alpaca",
            strategy_name="momentum",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 8),
            policy_version="12e_policy_v1",
            feature_version="11c_v1",
            replay_version="12c_v1",
            label_version="12d_v1",
            row_count=8,
            feature_keys_json=["feature_alpha", "feature_beta"],
            build_metadata_json={"seed": "ml_scoring"},
        )
    )
    start = datetime(2026, 1, 1, 10, tzinfo=UTC)
    for index in range(8):
        is_positive = index >= 4
        feature_alpha = float(index)
        feature_beta = float(index) * 0.5
        session.add(
            TrainingDatasetRow(
                dataset_version="12f_dataset_v1",
                row_key=f"row-{index}",
                decision_date=date(2026, 1, 1) + timedelta(days=index),
                symbol="AAPL" if index % 2 == 0 else "MSFT",
                asset_class=AssetClass.STOCK,
                timeframe="1h",
                strategy_name="momentum",
                source_label="alpaca",
                entry_candle_time=start + timedelta(days=index),
                feature_version="11c_v1",
                replay_version="12c_v1",
                label_version="12d_v1",
                feature_values_json={
                    "feature_alpha": feature_alpha,
                    "feature_beta": feature_beta,
                },
                label_values_json={"achieved_label": is_positive},
                metadata_json={"seed_index": index},
            )
        )
    session.commit()


def _write_persisted_bundle(
    *,
    artifact_dir: str,
    bundle_version: str,
    training_artifact_path: str,
    include_validation_reference: bool = True,
    strategy_name: str = "momentum",
) -> None:
    bundle_root = Path(artifact_dir) / "_persisted_model_bundles" / bundle_version
    bundle_root.mkdir(parents=True, exist_ok=True)
    references = [
        {
            "reference_type": "model_training",
            "reference_version": "12g_v1_model",
            "artifact_path": training_artifact_path,
        }
    ]
    if include_validation_reference:
        references.append(
            {
                "reference_type": "walkforward_validation",
                "reference_version": "12h_v1_validation",
            }
        )
    manifest = {
        "bundle_name": "baseline_model_bundle",
        "bundle_version": bundle_version,
        "dataset": {
            "dataset_version": "12f_dataset_v1",
            "feature_keys": ["feature_alpha", "feature_beta"],
        },
        "training_summary": {
            "model_version": "12g_v1_model",
            "model_family": "sklearn_gradient_boosting_classifier",
            "strategy_name": strategy_name,
            "trained_at": "2026-01-08T12:00:00+00:00",
            "artifact_path": training_artifact_path,
        },
        "validation_summary": {
            "aggregate_metrics": {
                "roc_auc": 0.81,
            }
        },
        "references": references,
    }
    (bundle_root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_ml_scoring_reranks_eligible_candidates_with_probability_blend() -> None:
    session = _build_session()
    _seed_dataset(session)
    with TemporaryDirectory() as temp_dir:
        trainer = HistoricalBaselineModelService(session, artifact_dir=temp_dir)
        training = trainer.train_for_dataset(dataset_version="12f_dataset_v1", strategy_name="momentum")
        service = HistoricalMLScoringService(
            session,
            artifact_dir=temp_dir,
            config=HistoricalMLScoringConfig(base_score_weight=0.5, ml_score_weight=0.5),
        )

        summary = service.score_candidates(
            dataset_version="12f_dataset_v1",
            strategy_name="momentum",
            artifact_path=training.artifact_path or "",
            candidates=[
                MLScoringCandidateInput(
                    symbol="AAPL",
                    asset_class="stock",
                    timeframe="1h",
                    candle_time=datetime(2026, 1, 10, 10, tzinfo=UTC),
                    source_label="alpaca",
                    strategy_name="momentum",
                    base_rank=1,
                    base_score=0.86,
                    feature_values={"feature_alpha": 2.0, "feature_beta": 1.0},
                ),
                MLScoringCandidateInput(
                    symbol="MSFT",
                    asset_class="stock",
                    timeframe="1h",
                    candle_time=datetime(2026, 1, 10, 10, tzinfo=UTC),
                    source_label="alpaca",
                    strategy_name="momentum",
                    base_rank=2,
                    base_score=0.78,
                    feature_values={"feature_alpha": 7.0, "feature_beta": 3.5},
                ),
            ],
        )

    assert summary.rows_scored == 2
    assert summary.rows_skipped == 0
    assert summary.candidates[0].symbol == "MSFT"
    assert summary.candidates[0].ml_probability is not None
    assert summary.candidates[0].combined_score > summary.candidates[1].combined_score
    assert summary.candidates[0].explanation

    contributions = [item.signed_contribution for item in summary.candidates[0].explanation]
    assert any(abs(value) > 0 for value in contributions)


def test_ml_scoring_does_not_promote_ineligible_or_incomplete_candidates() -> None:
    session = _build_session()
    _seed_dataset(session)
    with TemporaryDirectory() as temp_dir:
        trainer = HistoricalBaselineModelService(session, artifact_dir=temp_dir)
        training = trainer.train_for_dataset(dataset_version="12f_dataset_v1", strategy_name="momentum")
        service = HistoricalMLScoringService(session, artifact_dir=temp_dir)

        summary = service.score_candidates(
            dataset_version="12f_dataset_v1",
            strategy_name="momentum",
            artifact_path=training.artifact_path or "",
            candidates=[
                MLScoringCandidateInput(
                    symbol="NVDA",
                    asset_class="stock",
                    timeframe="1h",
                    candle_time=datetime(2026, 1, 10, 10, tzinfo=UTC),
                    source_label="alpaca",
                    strategy_name="momentum",
                    base_rank=1,
                    base_score=0.90,
                    feature_values={"feature_alpha": 6.0, "feature_beta": 3.0},
                ),
                MLScoringCandidateInput(
                    symbol="TSLA",
                    asset_class="stock",
                    timeframe="1h",
                    candle_time=datetime(2026, 1, 10, 10, tzinfo=UTC),
                    source_label="alpaca",
                    strategy_name="momentum",
                    base_rank=2,
                    base_score=0.88,
                    feature_values={"feature_alpha": 9.0},
                ),
                MLScoringCandidateInput(
                    symbol="AMD",
                    asset_class="stock",
                    timeframe="1h",
                    candle_time=datetime(2026, 1, 10, 10, tzinfo=UTC),
                    source_label="alpaca",
                    strategy_name="momentum",
                    base_rank=3,
                    base_score=0.87,
                    feature_values={"feature_alpha": 8.0, "feature_beta": 4.0},
                    eligible=False,
                ),
            ],
        )

    assert summary.rows_scored == 1
    assert summary.rows_skipped == 2
    assert summary.candidates[0].symbol == "NVDA"
    assert summary.candidates[1].scoring_skipped_reason == "missing_required_features"
    assert summary.candidates[2].scoring_skipped_reason == "deterministic_ineligible"


def test_ml_scoring_is_deterministic_for_same_inputs() -> None:
    session = _build_session()
    _seed_dataset(session)
    with TemporaryDirectory() as temp_dir:
        trainer = HistoricalBaselineModelService(session, artifact_dir=temp_dir)
        training = trainer.train_for_dataset(dataset_version="12f_dataset_v1", strategy_name="momentum")
        service = HistoricalMLScoringService(session, artifact_dir=temp_dir)
        candidates = [
            MLScoringCandidateInput(
                symbol="META",
                asset_class="stock",
                timeframe="1h",
                candle_time=datetime(2026, 1, 10, 10, tzinfo=UTC),
                source_label="alpaca",
                strategy_name="momentum",
                base_rank=1,
                base_score=0.80,
                feature_values={"feature_alpha": 5.0, "feature_beta": 2.5},
            )
        ]

        first = service.score_candidates(
            dataset_version="12f_dataset_v1",
            strategy_name="momentum",
            artifact_path=training.artifact_path or "",
            candidates=candidates,
        )
        second = service.score_candidates(
            dataset_version="12f_dataset_v1",
            strategy_name="momentum",
            artifact_path=training.artifact_path or "",
            candidates=candidates,
        )

    assert first.scoring_version == second.scoring_version
    assert first.candidates[0].combined_score == second.candidates[0].combined_score
    assert first.candidates[0].explanation == second.candidates[0].explanation


def test_ml_scoring_shadow_mode_preserves_deterministic_order() -> None:
    session = _build_session()
    _seed_dataset(session)
    with TemporaryDirectory() as temp_dir:
        trainer = HistoricalBaselineModelService(session, artifact_dir=temp_dir)
        training = trainer.train_for_dataset(dataset_version="12f_dataset_v1", strategy_name="momentum")
        _write_persisted_bundle(
            artifact_dir=temp_dir,
            bundle_version="12n_shadow_bundle",
            training_artifact_path=training.artifact_path or "",
        )
        service = HistoricalMLScoringService(session, artifact_dir=temp_dir)

        summary = service.score_candidates(
            dataset_version="12f_dataset_v1",
            strategy_name="momentum",
            artifact_path=training.artifact_path or "",
            bundle_version="12n_shadow_bundle",
            runtime_control_config=HistoricalMLRuntimeControlConfig(requested_mode="shadow"),
            candidates=[
                MLScoringCandidateInput(
                    symbol="AAPL",
                    asset_class="stock",
                    timeframe="1h",
                    candle_time=datetime(2026, 1, 10, 10, tzinfo=UTC),
                    source_label="alpaca",
                    strategy_name="momentum",
                    base_rank=1,
                    base_score=0.95,
                    feature_values={"feature_alpha": 2.0, "feature_beta": 1.0},
                ),
                MLScoringCandidateInput(
                    symbol="MSFT",
                    asset_class="stock",
                    timeframe="1h",
                    candle_time=datetime(2026, 1, 10, 10, tzinfo=UTC),
                    source_label="alpaca",
                    strategy_name="momentum",
                    base_rank=2,
                    base_score=0.75,
                    feature_values={"feature_alpha": 7.0, "feature_beta": 3.5},
                ),
            ],
        )

    assert summary.runtime_control is not None
    assert summary.runtime_control.effective_mode == "shadow"
    assert [row.symbol for row in summary.candidates] == ["AAPL", "MSFT"]
    assert summary.candidates[0].combined_score == summary.candidates[0].base_score
    assert summary.candidates[1].combined_score == summary.candidates[1].base_score
    assert summary.candidates[0].ml_probability is not None
    assert summary.candidates[0].runtime_reason_codes == ["shadow_mode"]


def test_ml_scoring_runtime_block_surfaces_reason_codes_and_fallback() -> None:
    session = _build_session()
    _seed_dataset(session)
    with TemporaryDirectory() as temp_dir:
        trainer = HistoricalBaselineModelService(session, artifact_dir=temp_dir)
        training = trainer.train_for_dataset(dataset_version="12f_dataset_v1", strategy_name="momentum")
        _write_persisted_bundle(
            artifact_dir=temp_dir,
            bundle_version="12n_blocked_bundle",
            training_artifact_path=training.artifact_path or "",
            include_validation_reference=False,
        )
        service = HistoricalMLScoringService(session, artifact_dir=temp_dir)

        summary = service.score_candidates(
            dataset_version="12f_dataset_v1",
            strategy_name="momentum",
            artifact_path=training.artifact_path or "",
            bundle_version="12n_blocked_bundle",
            runtime_control_config=HistoricalMLRuntimeControlConfig(requested_mode="active_rank_only"),
            candidates=[
                MLScoringCandidateInput(
                    symbol="MSFT",
                    asset_class="stock",
                    timeframe="1h",
                    candle_time=datetime(2026, 1, 10, 10, tzinfo=UTC),
                    source_label="alpaca",
                    strategy_name="momentum",
                    base_rank=2,
                    base_score=0.75,
                    feature_values={"feature_alpha": 7.0, "feature_beta": 3.5},
                ),
                MLScoringCandidateInput(
                    symbol="AAPL",
                    asset_class="stock",
                    timeframe="1h",
                    candle_time=datetime(2026, 1, 10, 10, tzinfo=UTC),
                    source_label="alpaca",
                    strategy_name="momentum",
                    base_rank=1,
                    base_score=0.95,
                    feature_values={"feature_alpha": 2.0, "feature_beta": 1.0},
                ),
            ],
        )

    assert summary.runtime_control is not None
    assert summary.runtime_control.effective_mode == "blocked"
    assert "validation_reference_missing" in summary.runtime_control.reason_codes
    assert summary.rows_scored == 0
    assert summary.rows_skipped == 2
    assert [row.symbol for row in summary.candidates] == ["AAPL", "MSFT"]
    assert all(row.scoring_skipped_reason == "ml_runtime_blocked" for row in summary.candidates)
    assert all("validation_reference_missing" in row.runtime_reason_codes for row in summary.candidates)
    assert all(row.ml_probability is None for row in summary.candidates)
