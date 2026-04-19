from __future__ import annotations

import json
import shutil
from contextlib import contextmanager
from dataclasses import asdict
from datetime import UTC, date, datetime
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


BUNDLE_ROOT = Path(gettempdir()) / "ai_trader_ml_artifacts" / "_persisted_model_bundles"
PRIMARY_BUNDLE = "12p_primary_bundle"
SECONDARY_BUNDLE = "12p_secondary_bundle"


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
    session.add(
        TrainingDatasetRow(
            dataset_version=dataset.dataset_version,
            row_key="row_1",
            decision_date=date(2026, 4, 1),
            symbol="AAPL",
            asset_class="stock",
            timeframe="1d",
            strategy_name="momentum",
            source_label="alpaca",
            entry_candle_time=datetime(2026, 4, 1, 14, 30, tzinfo=UTC),
            feature_version="12b_v1",
            replay_version="12c_v1",
            label_version="12d_v1",
            feature_values_json={"feature_alpha": 0.1, "feature_beta": 0.2},
            label_values_json={"label_primary": 1},
            metadata_json={"base_score": 0.55},
        )
    )
    session.commit()


def _write_bundle(bundle_version: str) -> None:
    bundle_path = BUNDLE_ROOT / bundle_version
    bundle_path.mkdir(parents=True, exist_ok=True)
    model = GradientBoostingClassifier(random_state=42)
    model.fit([[0.1, 0.2], [0.8, 1.0]], [0, 1])
    artifact_record = BaselineModelArtifactRecord(
        model_version=f"{bundle_version}_model",
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
        metrics={"roc_auc": 0.81},
        artifact_path=str(bundle_path / "model_artifact.joblib"),
        trained_at=datetime(2026, 4, 18, 12, 0, tzinfo=UTC),
    )
    joblib.dump({"artifact": artifact_record, "model": model}, bundle_path / "model_artifact.joblib")
    manifest = {
        "bundle_name": "baseline_model_bundle",
        "bundle_version": bundle_version,
        "dataset": {
            "dataset_version": "12f_dataset_v1",
            "feature_version": "12b_v1",
            "label_version": "12d_v1",
            "policy_version": "12e_v1",
            "replay_version": "12c_v1",
            "start_date": "2026-04-01",
            "end_date": "2026-04-04",
            "row_count": 1,
            "feature_keys": ["feature_alpha", "feature_beta"],
        },
        "training_summary": {
            **asdict(artifact_record),
            "rows_considered": 1,
            "rows_trained": 1,
            "positive_rows": 1,
            "negative_rows": 0,
            "skipped_reason": None,
        },
        "references": [
            {"reference_type": "model_training", "reference_version": artifact_record.model_version, "artifact_path": str(bundle_path / "model_artifact.joblib")},
            {"reference_type": "walkforward_validation", "reference_version": f"{bundle_version}_validation"},
        ],
    }
    (bundle_path / "manifest.json").write_text(json.dumps(manifest, default=str), encoding="utf-8")


@contextmanager
def _test_client(monkeypatch):
    monkeypatch.setattr(Redis, "from_url", lambda *args, **kwargs: FakeRedis())
    shutil.rmtree(BUNDLE_ROOT, ignore_errors=True)

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
    _write_bundle(PRIMARY_BUNDLE)
    _write_bundle(SECONDARY_BUNDLE)
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


def test_ml_deployment_state_and_promotion_flow(monkeypatch) -> None:
    with _test_client(monkeypatch) as client:
        initial = client.get("/api/ai/ml/deployment/state")
        approve = client.post(f"/api/ai/ml/deployment/approve/{PRIMARY_BUNDLE}", json={"actor": "tester", "notes": "walk-forward passed"})
        promote = client.post(f"/api/ai/ml/deployment/promote/{PRIMARY_BUNDLE}", json={"actor": "tester", "notes": "promote primary"})
        approve_second = client.post(f"/api/ai/ml/deployment/approve/{SECONDARY_BUNDLE}", json={"actor": "tester"})
        promote_second = client.post(f"/api/ai/ml/deployment/promote/{SECONDARY_BUNDLE}", json={"actor": "tester", "notes": "promote secondary"})
        rollback = client.post("/api/ai/ml/deployment/rollback", json={"actor": "tester", "notes": "rollback regression"})

    assert initial.status_code == 200
    assert initial.json()["active_bundle_version"] is None

    assert approve.status_code == 200
    assert PRIMARY_BUNDLE in approve.json()["state"]["approved_candidate_versions"]
    assert approve.json()["event"]["action"] == "candidate_approved"

    assert promote.status_code == 200
    assert promote.json()["state"]["active_bundle_version"] == PRIMARY_BUNDLE
    assert promote.json()["event"]["action"] == "bundle_promoted"

    assert approve_second.status_code == 200
    assert promote_second.status_code == 200
    assert promote_second.json()["state"]["active_bundle_version"] == SECONDARY_BUNDLE

    assert rollback.status_code == 200
    assert rollback.json()["state"]["active_bundle_version"] == PRIMARY_BUNDLE
    assert rollback.json()["event"]["action"] == "bundle_rolled_back"


def test_ml_deployment_freeze_blocks_promotion_until_unfrozen(monkeypatch) -> None:
    with _test_client(monkeypatch) as client:
        client.post(f"/api/ai/ml/deployment/approve/{PRIMARY_BUNDLE}", json={"actor": "tester"})
        client.post(f"/api/ai/ml/deployment/promote/{PRIMARY_BUNDLE}", json={"actor": "tester"})
        freeze = client.post(f"/api/ai/ml/deployment/freeze/{PRIMARY_BUNDLE}", json={"actor": "tester", "reason": "paper trading lock"})
        client.post(f"/api/ai/ml/deployment/approve/{SECONDARY_BUNDLE}", json={"actor": "tester"})
        blocked = client.post(f"/api/ai/ml/deployment/promote/{SECONDARY_BUNDLE}", json={"actor": "tester"})
        unfreeze = client.post("/api/ai/ml/deployment/unfreeze", json={"actor": "tester", "notes": "lock cleared"})
        promote = client.post(f"/api/ai/ml/deployment/promote/{SECONDARY_BUNDLE}", json={"actor": "tester"})

    assert freeze.status_code == 200
    assert freeze.json()["state"]["frozen_bundle_version"] == PRIMARY_BUNDLE
    assert freeze.json()["state"]["freeze_reason"] == "paper trading lock"

    assert blocked.status_code == 409
    assert "frozen" in blocked.json()["detail"]

    assert unfreeze.status_code == 200
    assert unfreeze.json()["state"]["frozen_bundle_version"] is None
    assert unfreeze.json()["event"]["action"] == "bundle_unfrozen"

    assert promote.status_code == 200
    assert promote.json()["state"]["active_bundle_version"] == SECONDARY_BUNDLE
