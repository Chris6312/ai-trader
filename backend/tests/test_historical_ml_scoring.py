from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from tempfile import TemporaryDirectory

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.ai_research import TrainingDatasetRow, TrainingDatasetVersion
from app.models.trading import AssetClass
from app.services.historical.historical_baseline_model import HistoricalBaselineModelService
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
