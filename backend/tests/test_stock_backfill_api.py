from __future__ import annotations

from fastapi.testclient import TestClient
from redis import Redis

from app.main import app


class FakeRedis:
    def __init__(self) -> None:
        self.storage: dict[str, str] = {}

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.storage[key] = value

    def get(self, key: str) -> str | None:
        return self.storage.get(key)


def test_stock_backfill_policy_endpoint_returns_default_policy(monkeypatch) -> None:
    monkeypatch.setattr(Redis, "from_url", lambda *args, **kwargs: FakeRedis())

    with TestClient(app) as client:
        response = client.get("/api/ai/backfill/stocks/policy")

    assert response.status_code == 200
    payload = response.json()
    assert payload["policy_version"] == "12q_stock_policy_v1"
    assert payload["policy_name"] == "ml_stock_history_defaults"
    assert payload["asset_class"] == "stock"
    assert payload["symbol_source"] == "active_registry"
    assert payload["max_symbols_per_run"] == 200
    assert payload["max_parallel_fetches"] == 5
    assert payload["timeframes"]["15m"]["lookback_days"] == 60
    assert payload["timeframes"]["15m"]["lookback_label"] == "60 trading days"
    assert payload["timeframes"]["1d"]["lookback_days"] == 730
