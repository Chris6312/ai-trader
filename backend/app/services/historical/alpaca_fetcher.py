from __future__ import annotations

from datetime import UTC, datetime
from typing import Iterable

import httpx

from app.core.config import get_settings
from app.services.historical.normalization import (
    alpaca_timeframe_for,
    ensure_utc,
    normalize_alpaca_bar,
)
from app.services.historical.rate_limiter import RateLimiter
from app.services.historical.schemas import HistoricalCandleRecord


class AlpacaHistoricalFetcher:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        api_secret: str | None = None,
        default_feed: str | None = None,
        batch_size: int | None = None,
        rate_limiter: RateLimiter | None = None,
        timeout_seconds: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        settings = get_settings()

        self.base_url = (base_url or settings.alpaca_market_data_base_url).rstrip("/")
        self.api_key = api_key or settings.alpaca_api_key
        self.api_secret = api_secret or settings.alpaca_api_secret
        self.default_feed = default_feed or settings.alpaca_default_feed
        self.batch_size = batch_size or settings.alpaca_stock_batch_size
        self.timeout_seconds = timeout_seconds
        self.rate_limiter = rate_limiter or RateLimiter(
            max_calls=settings.alpaca_rate_limit_per_minute,
            period_seconds=60.0,
        )
        self._client = client

    def fetch_batch(
        self,
        *,
        symbols: list[str],
        timeframe: str,
        start_at: datetime,
        end_at: datetime,
    ) -> list[HistoricalCandleRecord]:
        if not symbols:
            return []

        if end_at <= start_at:
            raise ValueError("end_at must be after start_at")

        all_rows: list[HistoricalCandleRecord] = []
        fetched_at = datetime.now(UTC)

        for chunk in _chunked(symbols, self.batch_size):
            all_rows.extend(
                self._fetch_chunk(
                    symbols=chunk,
                    timeframe=timeframe,
                    start_at=start_at,
                    end_at=end_at,
                    fetched_at=fetched_at,
                )
            )

        return sorted(all_rows, key=lambda row: (row.symbol, row.candle_time))

    def _fetch_chunk(
        self,
        *,
        symbols: list[str],
        timeframe: str,
        start_at: datetime,
        end_at: datetime,
        fetched_at: datetime,
    ) -> list[HistoricalCandleRecord]:
        endpoint = f"{self.base_url}/v2/stocks/bars"
        params = {
            "symbols": ",".join(symbols),
            "timeframe": alpaca_timeframe_for(timeframe),
            "start": ensure_utc(start_at).isoformat().replace("+00:00", "Z"),
            "end": ensure_utc(end_at).isoformat().replace("+00:00", "Z"),
            "limit": 10000,
            "feed": self.default_feed,
            "adjustment": "raw",
            "sort": "asc",
        }
        headers = {
            "APCA-API-KEY-ID": self.api_key or "",
            "APCA-API-SECRET-KEY": self.api_secret or "",
        }

        records: list[HistoricalCandleRecord] = []
        page_token: str | None = None

        with self._get_client() as client:
            while True:
                request_params = dict(params)
                if page_token:
                    request_params["page_token"] = page_token

                self.rate_limiter.acquire()
                response = client.get(endpoint, params=request_params, headers=headers)
                response.raise_for_status()
                payload = response.json()

                for symbol, bars in payload.get("bars", {}).items():
                    for bar in bars:
                        records.append(
                            normalize_alpaca_bar(
                                symbol=symbol,
                                timeframe=timeframe,
                                bar=bar,
                                fetched_at=fetched_at,
                            )
                        )

                page_token = payload.get("next_page_token")
                if not page_token:
                    break

        return records

    def _get_client(self):
        if self._client is not None:
            return _NoCloseClientContext(self._client)
        return httpx.Client(timeout=self.timeout_seconds)


class _NoCloseClientContext:
    def __init__(self, client: httpx.Client) -> None:
        self.client = client

    def __enter__(self) -> httpx.Client:
        return self.client

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def _chunked(values: list[str], size: int) -> Iterable[list[str]]:
    if size <= 0:
        raise ValueError("size must be positive")
    for index in range(0, len(values), size):
        yield values[index : index + size]