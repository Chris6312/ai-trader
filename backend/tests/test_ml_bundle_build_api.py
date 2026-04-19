from __future__ import annotations

import shutil
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from tempfile import gettempdir

from fastapi.testclient import TestClient
from redis import Redis
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.main import app
from app.models import AssetClass
from app.models.ai_research import TrainingDatasetRow, TrainingDatasetVersion


class FakeRedis:
    def __init__(self) -> None:
        self.storage: dict[str, str] = {}

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.storage[key] = value

    def get(self, key: str) -> str | None:
        return self.storage.get(key)


BUNDLE_ROOT = Path(gettempdir()) / "ai_trader_ml_artifacts" / "_persisted_model_bundles"


def _seed_training_dataset(session: Session) -> None:
    dataset = TrainingDatasetVersion(
        dataset_version="12f_live_bundle_dataset_v1",
        dataset_name="historical_training_dataset",
        dataset_definition_version="12f_v1",
        asset_class=AssetClass.STOCK,
        timeframe="1d",
        source_label="alpaca",
        strategy_name="momentum",
        start_date=date(2026, 4, 1),
        end_date=date(2026, 4, 8),
        policy_version="12e_policy_v1",
        feature_version="11c_v1",
        replay_version="12c_v1",
        label_version="12d_v1",
        row_count=8,
        feature_keys_json=["feature_alpha", "feature_beta"],
        build_metadata_json={"source": "test"},
    )
    session.add(dataset)

    start = datetime(2026, 4, 1, 14, 30, tzinfo=UTC)
    for index in range(8):
        is_positive = index >= 4
        session.add(
            TrainingDatasetRow(
                dataset_version=dataset.dataset_version,
                row_key=f"row_{index}",
                decision_date=(start + timedelta(days=index)).date(),
                symbol=f"SYM{index}",
                asset_class=AssetClass.STOCK,
                timeframe="1d",
                strategy_name="momentum",
                source_label="alpaca",
                entry_candle_time=start + timedelta(days=index),
                feature_version="11c_v1",
                replay_version="12c_v1",
                label_version="12d_v1",
                feature_values_json={
                    "feature_alpha": 0.1 + index * 0.1,
                    "feature_beta": 0.2 + index * 0.15,
                },
                label_values_json={"achieved_label": is_positive},
                metadata_json={"base_score": 0.45 + index * 0.05},
            )
        )
    session.commit()


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
    _seed_training_dataset(session)
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


def test_ml_bundle_build_persists_bundle_for_registry(monkeypatch) -> None:
    with _test_client(monkeypatch) as client:
        build_response = client.post(
            "/api/ai/ml/bundles/build",
            json={
                "dataset_version": "12f_live_bundle_dataset_v1",
                "strategy_name": "momentum",
                "include_drift_review": True,
            },
        )
        registry_response = client.get("/api/ai/ml/models")

    assert build_response.status_code == 200
    build_payload = build_response.json()
    assert build_payload["dataset_version"] == "12f_live_bundle_dataset_v1"
    assert build_payload["strategy_name"] == "momentum"
    assert build_payload["verified_bundle"] is True
    assert Path(build_payload["manifest_path"]).exists()

    assert registry_response.status_code == 200
    registry_rows = registry_response.json()["rows"]
    assert any(row["bundle_version"] == build_payload["bundle_version"] for row in registry_rows)
