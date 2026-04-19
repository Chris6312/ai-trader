from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import AssetClass
from app.models.ai_research import TrainingDatasetRow, TrainingDatasetVersion
from app.services.historical.historical_baseline_model import HistoricalBaselineModelService


def _build_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed_dataset(session: Session, *, dataset_version: str = "12f_v1_seed") -> None:
    session.add(
        TrainingDatasetVersion(
            dataset_version=dataset_version,
            dataset_name="baseline_training_dataset",
            dataset_definition_version="12f_v1",
            asset_class=AssetClass.STOCK,
            timeframe="1h",
            source_label="alpaca",
            strategy_name="momentum",
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 18),
            policy_version="12e_policy_v1",
            feature_version="11c_v1",
            replay_version="12c_v1",
            label_version="12d_v1",
            row_count=4,
            feature_keys_json=["close_vs_sma_20", "volume_ratio_5"],
            build_metadata_json={"rows_considered": 4},
        )
    )
    rows = [
        ("AAPL", True, "0.08", "1.9"),
        ("MSFT", False, "-0.03", "0.8"),
        ("NVDA", True, "0.05", "1.5"),
        ("AMD", False, "-0.02", "0.7"),
    ]
    for index, (symbol, achieved_label, close_vs_sma_20, volume_ratio_5) in enumerate(rows):
        session.add(
            TrainingDatasetRow(
                dataset_version=dataset_version,
                row_key=f"row_{index}",
                decision_date=date(2026, 4, 18),
                symbol=symbol,
                asset_class=AssetClass.STOCK,
                timeframe="1h",
                strategy_name="momentum",
                source_label="alpaca",
                entry_candle_time=datetime(2026, 4, 18, 12 + index, 0, tzinfo=UTC),
                feature_version="11c_v1",
                replay_version="12c_v1",
                label_version="12d_v1",
                feature_values_json={
                    "close_vs_sma_20": close_vs_sma_20,
                    "volume_ratio_5": volume_ratio_5,
                },
                label_values_json={
                    "achieved_label": achieved_label,
                    "is_trade_profitable": achieved_label,
                },
                metadata_json={"feature_candle_time": datetime(2026, 4, 18, 11 + index, 0, tzinfo=UTC).isoformat()},
            )
        )
    session.flush()


def test_historical_baseline_model_trains_and_writes_artifact() -> None:
    session = _build_session()
    _seed_dataset(session)
    with TemporaryDirectory() as temp_dir:
        service = HistoricalBaselineModelService(session, artifact_dir=temp_dir)
        summary = service.train_for_dataset(dataset_version="12f_v1_seed", strategy_name="momentum")

        assert summary.model_version is not None
        assert summary.rows_considered == 4
        assert summary.rows_trained == 4
        assert summary.positive_rows == 2
        assert summary.negative_rows == 2
        assert summary.feature_keys == ["close_vs_sma_20", "volume_ratio_5"]
        assert summary.artifact_path is not None
        assert Path(summary.artifact_path).exists()

        artifact = service.load_artifact(summary.artifact_path)
        assert artifact["artifact"].dataset_version == "12f_v1_seed"
        assert artifact["artifact"].strategy_name == "momentum"
        assert artifact["artifact"].feature_keys == ["close_vs_sma_20", "volume_ratio_5"]


def test_historical_baseline_model_skips_single_class_dataset() -> None:
    session = _build_session()
    _seed_dataset(session, dataset_version="12f_v1_single_class")
    rows = list(
        session.query(TrainingDatasetRow).filter(TrainingDatasetRow.dataset_version == "12f_v1_single_class")
    )
    for row in rows:
        row.label_values_json = {"achieved_label": True}
    session.flush()

    with TemporaryDirectory() as temp_dir:
        service = HistoricalBaselineModelService(session, artifact_dir=temp_dir)
        summary = service.train_for_dataset(dataset_version="12f_v1_single_class", strategy_name="momentum")

        assert summary.model_version is None
        assert summary.skipped_reason == "single_class_labels"
        assert summary.rows_trained == 4
