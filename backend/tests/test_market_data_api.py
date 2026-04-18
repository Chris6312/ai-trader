from __future__ import annotations

import json

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


def test_fetch_audit_endpoint_reports_single_worker_policy(monkeypatch) -> None:
    monkeypatch.setattr(Redis, "from_url", lambda *args, **kwargs: FakeRedis())

    client = TestClient(app)
    response = client.get("/api/market-data/fetch-audit")

    assert response.status_code == 200
    payload = response.json()
    assert payload["closed_candle_owner"] == "candle_worker"
    assert payload["duplicate_fetch_paths_detected"] is False
    assert payload["quote_read_paths_allowed"] is True


def test_cached_quote_endpoint_returns_404_when_quote_missing(monkeypatch) -> None:
    monkeypatch.setattr(Redis, "from_url", lambda *args, **kwargs: FakeRedis())

    client = TestClient(app)
    response = client.get("/api/market-data/cached-quote", params={"symbol": "BTC/USD"})

    assert response.status_code == 404


def test_cached_quote_endpoint_returns_cached_payload(monkeypatch) -> None:
    fake_redis = FakeRedis()
    fake_redis.set(
        "market-data:quote:BTC/USD",
        json.dumps(
            {
                "provider": "kraken",
                "asset_class": "crypto",
                "symbol": "BTC/USD",
                "bid": "64000",
                "ask": "64010",
                "last": "64005",
                "mark": "64005",
                "volume_24h": "100",
                "as_of": "2026-04-17T21:05:00+00:00",
            }
        ),
    )
    monkeypatch.setattr(Redis, "from_url", lambda *args, **kwargs: fake_redis)

    client = TestClient(app)
    response = client.get("/api/market-data/cached-quote", params={"symbol": "BTC/USD"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "BTC/USD"
    assert payload["provider"] == "kraken"


def test_health_summary_endpoint_returns_symbol_statuses(monkeypatch) -> None:
    fake_redis = FakeRedis()
    fake_redis.set(
        "market-data:quote:BTC/USD",
        json.dumps(
            {
                "provider": "kraken",
                "asset_class": "crypto",
                "symbol": "BTC/USD",
                "bid": "64000",
                "ask": "64010",
                "last": "64005",
                "mark": "64005",
                "volume_24h": "100",
                "as_of": "2026-04-17T21:05:00+00:00",
            }
        ),
    )
    monkeypatch.setattr(Redis, "from_url", lambda *args, **kwargs: fake_redis)

    client = TestClient(app)
    response = client.get("/api/market-data/health-summary")

    assert response.status_code == 200
    payload = response.json()
    assert "symbols" in payload
    assert payload["worker_enabled"] in (True, False)
    assert len(payload["symbols"]) >= 1
