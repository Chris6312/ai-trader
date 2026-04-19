from __future__ import annotations

import json
import shutil
from contextlib import contextmanager
from dataclasses import asdict
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from tempfile import gettempdir

import joblib
from fastapi.testclient import TestClient
from redis import Redis
from sklearn.ensemble import GradientBoostingClassifier
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.main import app
from app.models.ai_research import TrainingDatasetRow, TrainingDatasetVersion
from app.services.historical.historical_baseline_model_schemas import BaselineModelArtifactRecord


class FakeRedis:
    def __init__(self) -> None:
        self.storage: dict[str, str] = {}

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.storage[key] = value

    def get(self, key: str) -> str | None:
        return self.storage.get(key)


BUNDLE_VERSION = "12l_v1_transparency_test"
BUNDLE_ROOT = Path(gettempdir()) / "ai_trader_ml_artifacts" / "_persisted_model_bundles" / BUNDLE_VERSION


def _seed_dataset(session: Session) -> None:
    dataset = TrainingDatasetVersion(
        dataset_version="12f_dataset_v1",
        dataset_name="historical_training_dataset",
        dataset_definition_version="12f_v1",
        asset_class="stock",
        timeframe="1d",
        source_label="alpaca",
        strategy_name="momentum",
        start_date=date(2026, 4, 1),
        end_date=date(2026, 4, 4),
        policy_version="12e_v1",
        feature_version="12b_v1",
        replay_version="12c_v1",
        label_version="12d_v1",
        row_count=4,
        feature_keys_json=["feature_alpha", "feature_beta"],
        build_metadata_json={"source": "test"},
    )
    session.add(dataset)
    rows = [
        TrainingDatasetRow(
            dataset_version=dataset.dataset_version,
            row_key=f"row_{index}",
            decision_date=date(2026, 4, index + 1),
            symbol=symbol,
            asset_class="stock",
            timeframe="1d",
            strategy_name="momentum",
            source_label="alpaca",
            entry_candle_time=datetime(2026, 4, index + 1, 14, 30, tzinfo=UTC),
            feature_version="12b_v1",
            replay_version="12c_v1",
            label_version="12d_v1",
            feature_values_json={
                "feature_alpha": alpha,
                "feature_beta": beta,
            },
            label_values_json={"label_primary": label},
            metadata_json={"base_score": base_score},
        )
        for index, (symbol, alpha, beta, label, base_score) in enumerate(
            [
                ("AAPL", 0.10, 0.30, 0, 0.45),
                ("MSFT", 0.20, 0.50, 0, 0.50),
                ("NVDA", 0.80, 1.20, 1, 0.70),
                ("AMD", 0.90, 1.40, 1, 0.75),
            ]
        )
    ]
    session.add_all(rows)
    session.commit()


def _write_bundle_artifacts() -> None:
    shutil.rmtree(BUNDLE_ROOT, ignore_errors=True)
    BUNDLE_ROOT.mkdir(parents=True, exist_ok=True)

    X = [[0.10, 0.30], [0.20, 0.50], [0.80, 1.20], [0.90, 1.40]]
    y = [0, 0, 1, 1]
    model = GradientBoostingClassifier(random_state=42)
    model.fit(X, y)

    artifact_record = BaselineModelArtifactRecord(
        model_version="12g_v1_model",
        model_family="sklearn_gradient_boosting_classifier",
        strategy_name="momentum",
        dataset_version="12f_dataset_v1",
        policy_version="12e_v1",
        feature_version="12b_v1",
        label_version="12d_v1",
        feature_keys=["feature_alpha", "feature_beta"],
        label_key="label_primary",
        training_window_start="2026-04-01",
        training_window_end="2026-04-04",
        hyperparameters={"random_state": 42},
        metrics={"roc_auc": 0.82, "accuracy": 0.75},
        artifact_path=str(BUNDLE_ROOT / "model_artifact.joblib"),
        trained_at=datetime(2026, 4, 18, 12, 0, tzinfo=UTC),
    )
    joblib.dump({"artifact": artifact_record, "model": model}, BUNDLE_ROOT / "model_artifact.joblib")

    drift_payload = {
        "global_feature_importance": [
            {"feature_key": "feature_beta", "tree_importance": 0.7, "permutation_importance": 0.6},
            {"feature_key": "feature_alpha", "tree_importance": 0.3, "permutation_importance": 0.2},
        ],
        "regime_feature_importance": [
            {"feature_key": "regime_trend_flag", "tree_importance": 0.4, "permutation_importance": 0.3}
        ],
        "global_drift_metrics": [
            {
                "feature_key": "feature_beta",
                "population_stability_index": 0.12,
                "standardized_mean_shift": 0.55,
                "drift_flagged": True,
            }
        ],
    }
    drift_path = BUNDLE_ROOT / "12i_drift_review.json"
    drift_path.write_text(json.dumps(drift_payload), encoding="utf-8")

    manifest = {
        "bundle_name": "baseline_model_bundle",
        "bundle_version": BUNDLE_VERSION,
        "dataset": {
            "dataset_version": "12f_dataset_v1",
            "feature_version": "12b_v1",
            "label_version": "12d_v1",
            "policy_version": "12e_v1",
            "replay_version": "12c_v1",
            "start_date": "2026-04-01",
            "end_date": "2026-04-04",
            "row_count": 4,
            "feature_keys": ["feature_alpha", "feature_beta"],
        },
        "training_summary": {
            **asdict(artifact_record),
            "rows_considered": 4,
            "rows_trained": 4,
            "positive_rows": 2,
            "negative_rows": 2,
            "skipped_reason": None,
        },
        "references": [
            {
                "reference_type": "model_training",
                "reference_version": "12g_v1_model",
                "artifact_path": str(BUNDLE_ROOT / "model_artifact.joblib"),
            },
            {
                "reference_type": "walkforward_validation",
                "reference_version": "12h_v1_validation",
            },
            {
                "reference_type": "feature_drift_review",
                "reference_version": "12i_v1_review",
                "artifact_path": str(drift_path),
            },
            {
                "reference_type": "scoring_profile",
                "reference_version": "12j_v1_scoring",
            },
        ],
    }
    (BUNDLE_ROOT / "manifest.json").write_text(json.dumps(manifest, default=str), encoding="utf-8")


@contextmanager
def _test_client(monkeypatch):
    monkeypatch.setattr(Redis, "from_url", lambda *args, **kwargs: FakeRedis())

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    session = TestingSessionLocal()
    _seed_dataset(session)
    _write_bundle_artifacts()
    session.close()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    from app.db.session import get_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
        shutil.rmtree(BUNDLE_ROOT, ignore_errors=True)


def test_ml_transparency_registry_and_overview(monkeypatch) -> None:
    with _test_client(monkeypatch) as client:
        registry_response = client.get("/api/ai/ml/models")
        overview_response = client.get("/api/ai/ml/overview", params={"bundle_version": BUNDLE_VERSION})

    assert registry_response.status_code == 200
    registry_payload = registry_response.json()
    assert registry_payload["returned"] >= 1
    assert any(row["bundle_version"] == BUNDLE_VERSION for row in registry_payload["rows"])

    assert overview_response.status_code == 200
    overview_payload = overview_response.json()
    assert overview_payload["model"]["bundle_version"] == BUNDLE_VERSION
    assert overview_payload["model"]["validation_version"] == "12h_v1_validation"
    assert overview_payload["global_feature_importance"][0]["feature_key"] == "feature_beta"
    assert overview_payload["drift_signals"][0]["drift_flagged"] is True
    assert overview_payload["sample_rows"]




def test_ml_transparency_registry_uses_shared_artifact_verification(monkeypatch) -> None:
    with _test_client(monkeypatch) as client:
        manifest_path = BUNDLE_ROOT / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["training_summary"]["artifact_path"] = str(BUNDLE_ROOT / "missing_from_training_summary.joblib")
        manifest_path.write_text(json.dumps(manifest, default=str), encoding="utf-8")

        registry_response = client.get("/api/ai/ml/models")
        runtime_response = client.get(
            "/api/ai/ml/runtime",
            params={
                "bundle_version": BUNDLE_VERSION,
                "strategy_name": "momentum",
                "requested_mode": "active_rank_only",
            },
        )

    assert registry_response.status_code == 200
    assert runtime_response.status_code == 200
    registry_row = next(row for row in registry_response.json()["rows"] if row["bundle_version"] == BUNDLE_VERSION)
    runtime_payload = runtime_response.json()
    assert registry_row["verified_artifact"] is True
    assert runtime_payload["verified_artifact"] is True
    assert runtime_payload["metadata"]["artifact_source"] == "model_training_reference"

def test_ml_transparency_row_list_and_explanation(monkeypatch) -> None:
    with _test_client(monkeypatch) as client:
        rows_response = client.get("/api/ai/ml/rows", params={"bundle_version": BUNDLE_VERSION})
        rows_payload = rows_response.json()
        explanation_response = client.get(
            "/api/ai/ml/explanations/historical",
            params={"bundle_version": BUNDLE_VERSION, "row_key": rows_payload["rows"][0]["row_key"]},
        )

    assert rows_response.status_code == 200
    assert rows_payload["returned"] == 4
    assert rows_payload["rows"][0]["symbol"] in {"AAPL", "AMD", "MSFT", "NVDA"}

    assert explanation_response.status_code == 200
    explanation_payload = explanation_response.json()
    assert explanation_payload["bundle_version"] == BUNDLE_VERSION
    assert explanation_payload["row"]["row_key"] == rows_payload["rows"][0]["row_key"]
    assert explanation_payload["probability"] is not None
    assert explanation_payload["feature_snapshot"]["feature_alpha"] is not None
