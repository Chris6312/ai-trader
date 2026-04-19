from __future__ import annotations

import json
import shutil
from contextlib import contextmanager
from pathlib import Path
from tempfile import gettempdir

from fastapi.testclient import TestClient
from redis import Redis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.main import app


class FakeRedis:
    def __init__(self) -> None:
        self.storage: dict[str, str] = {}

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.storage[key] = value

    def get(self, key: str) -> str | None:
        return self.storage.get(key)


BUNDLE_VERSION = "12n_runtime_api"
BUNDLE_ROOT = Path(gettempdir()) / "ai_trader_ml_artifacts" / "_persisted_model_bundles" / BUNDLE_VERSION


def _write_bundle() -> None:
    shutil.rmtree(BUNDLE_ROOT, ignore_errors=True)
    BUNDLE_ROOT.mkdir(parents=True, exist_ok=True)
    artifact_path = BUNDLE_ROOT / "model_artifact.joblib"
    artifact_path.write_bytes(b"placeholder")
    manifest = {
        "bundle_name": "baseline_model_bundle",
        "bundle_version": BUNDLE_VERSION,
        "dataset": {
            "dataset_version": "12f_dataset_v1",
            "feature_keys": ["feature_alpha", "feature_beta"],
        },
        "training_summary": {
            "strategy_name": "momentum",
            "trained_at": "2026-04-18T12:00:00+00:00",
            "artifact_path": str(artifact_path),
        },
        "validation_summary": {
            "aggregate_metrics": {
                "roc_auc": 0.78,
            }
        },
        "references": [
            {
                "reference_type": "model_training",
                "reference_version": "12g_v1_model",
                "artifact_path": str(artifact_path),
            },
            {
                "reference_type": "walkforward_validation",
                "reference_version": "12h_v1_validation",
            },
        ],
    }
    (BUNDLE_ROOT / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


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
    _write_bundle()

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


def test_ml_runtime_endpoint_reports_shadow_and_blocked_states(monkeypatch) -> None:
    with _test_client(monkeypatch) as client:
        shadow = client.get(
            "/api/ai/ml/runtime",
            params={
                "bundle_version": BUNDLE_VERSION,
                "strategy_name": "momentum",
                "requested_mode": "shadow",
                "minimum_validation_metric": 0.70,
            },
        )
        blocked = client.get(
            "/api/ai/ml/runtime",
            params={
                "bundle_version": BUNDLE_VERSION,
                "strategy_name": "breakout",
                "requested_mode": "active_rank_only",
                "required_features": ["feature_alpha", "feature_gamma"],
            },
        )

    assert shadow.status_code == 200
    shadow_payload = shadow.json()
    assert shadow_payload["effective_mode"] == "shadow"
    assert shadow_payload["ranking_policy"] == "shadow_compare"
    assert shadow_payload["reason_codes"] == ["shadow_mode"]

    assert blocked.status_code == 200
    blocked_payload = blocked.json()
    assert blocked_payload["effective_mode"] == "blocked"
    assert set(blocked_payload["reason_codes"]) == {"strategy_mismatch", "missing_required_features"}
