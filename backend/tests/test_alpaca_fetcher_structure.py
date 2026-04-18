from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.models import AssetClass
from app.services.historical.alpaca_fetcher import AlpacaHistoricalFetcher
from app.services.historical.normalization import alpaca_timeframe_for, normalize_alpaca_bar


class FakeRateLimiter:
    def __init__(self) -> None:
        self.calls = 0

    def acquire(self) -> None:
        self.calls += 1


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class FakeClient:
    def __init__(self, payloads: list[dict]) -> None:
        self.payloads = payloads
        self.calls: list[dict] = []

    def get(self, url: str, *, params: dict, headers: dict):
        self.calls.append({"url": url, "params": params, "headers": headers})
        return FakeResponse(self.payloads.pop(0))


def test_alpaca_timeframe_mapping() -> None:
    assert alpaca_timeframe_for("15m") == "15Min"
    assert alpaca_timeframe_for("1h") == "1Hour"
    assert alpaca_timeframe_for("4h") == "4Hour"
    assert alpaca_timeframe_for("1d") == "1Day"


def test_normalize_alpaca_bar_builds_historical_candle_record() -> None:
    fetched_at = datetime(2026, 4, 18, 13, 0, tzinfo=UTC)
    row = normalize_alpaca_bar(
        symbol="aapl",
        timeframe="1d",
        bar={
            "t": "2026-04-17T00:00:00Z",
            "o": 201.25,
            "h": 204.0,
            "l": 200.5,
            "c": 203.75,
            "v": 123456,
        },
        fetched_at=fetched_at,
    )

    assert row.symbol == "AAPL"
    assert row.asset_class == AssetClass.STOCK
    assert row.timeframe == "1d"
    assert row.close == Decimal("203.75")
    assert row.source_label == "alpaca"
    assert row.retention_bucket == "macro"
    assert row.fetched_at == fetched_at


def test_fetch_batch_handles_pagination_and_rate_limiting() -> None:
    limiter = FakeRateLimiter()
    client = FakeClient(
        [
            {
                "bars": {
                    "AAPL": [
                        {
                            "t": "2026-04-17T13:30:00Z",
                            "o": 200,
                            "h": 202,
                            "l": 199,
                            "c": 201,
                            "v": 1000,
                        }
                    ]
                },
                "next_page_token": "page-2",
            },
            {
                "bars": {
                    "MSFT": [
                        {
                            "t": "2026-04-17T13:30:00Z",
                            "o": 300,
                            "h": 305,
                            "l": 299,
                            "c": 304,
                            "v": 2000,
                        }
                    ]
                },
                "next_page_token": None,
            },
        ]
    )
    fetcher = AlpacaHistoricalFetcher(
        base_url="https://data.alpaca.markets",
        api_key="key",
        api_secret="secret",
        default_feed="iex",
        batch_size=50,
        rate_limiter=limiter,
        client=client,
    )

    rows = fetcher.fetch_batch(
        symbols=["AAPL", "MSFT"],
        timeframe="15m",
        start_at=datetime(2026, 4, 17, 0, 0, tzinfo=UTC),
        end_at=datetime(2026, 4, 18, 0, 0, tzinfo=UTC),
    )

    assert len(rows) == 2
    assert [row.symbol for row in rows] == ["AAPL", "MSFT"]
    assert limiter.calls == 2
    assert client.calls[0]["params"]["timeframe"] == "15Min"
    assert client.calls[1]["params"]["page_token"] == "page-2"
