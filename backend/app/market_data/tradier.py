from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import httpx

from app.market_data.schemas import NormalizedCandle, NormalizedQuote, NormalizedSymbolMetadata
from app.models import AssetClass, CandleInterval, MarketDataProvider


class TradierMarketDataAdapter:
    def __init__(
        self,
        token: str | None = None,
        base_url: str = "https://api.tradier.com/v1/markets",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.token = token
        self.base_url = base_url.rstrip("/")
        self._client = client

    @property
    def is_configured(self) -> bool:
        return bool(self.token)

    async def fetch_history(self, symbol: str, interval: CandleInterval) -> list[NormalizedCandle]:
        payload = await self._get_json(
            "/history",
            params={"symbol": symbol, "interval": interval.value},
        )
        return self.parse_history_response(symbol=symbol, interval=interval, payload=payload)

    async def fetch_quote(self, symbol: str) -> NormalizedQuote:
        payload = await self._get_json("/quotes", params={"symbols": symbol, "greeks": "false"})
        return self.parse_quote_response(symbol=symbol, payload=payload)

    def parse_history_response(
        self,
        symbol: str,
        interval: CandleInterval,
        payload: dict[str, object],
    ) -> list[NormalizedCandle]:
        history = payload.get("history", {})
        rows = history.get("day", []) if isinstance(history, dict) else []
        candles: list[NormalizedCandle] = []

        for row in rows:
            if not isinstance(row, dict):
                continue

            open_time = datetime.fromisoformat(f"{row['date']}T00:00:00+00:00")
            close_time = datetime.fromisoformat(f"{row['date']}T23:59:59+00:00")
            candles.append(
                NormalizedCandle(
                    provider=MarketDataProvider.TRADIER,
                    asset_class=AssetClass.STOCK,
                    symbol=symbol,
                    interval=interval,
                    open_time=open_time,
                    close_time=close_time,
                    open_price=Decimal(str(row["open"])),
                    high_price=Decimal(str(row["high"])),
                    low_price=Decimal(str(row["low"])),
                    close_price=Decimal(str(row["close"])),
                    volume=Decimal(str(row.get("volume", 0))),
                    vwap=None,
                    trade_count=None,
                    is_closed=True,
                    source_updated_at=datetime.now(UTC),
                )
            )

        return candles

    def parse_quote_response(self, symbol: str, payload: dict[str, object]) -> NormalizedQuote:
        quotes = payload.get("quotes", {})
        quote = quotes.get("quote", {}) if isinstance(quotes, dict) else {}
        bid = self._decimal_or_none(quote.get("bid"))
        ask = self._decimal_or_none(quote.get("ask"))
        last = self._decimal_or_none(quote.get("last")) or Decimal("0")
        mark = last if bid is None or ask is None else (bid + ask) / Decimal("2")

        return NormalizedQuote(
            provider=MarketDataProvider.TRADIER,
            asset_class=AssetClass.STOCK,
            symbol=symbol,
            bid=bid,
            ask=ask,
            last=last,
            mark=mark,
            volume_24h=self._decimal_or_none(quote.get("volume")),
            as_of=datetime.now(UTC),
        )

    def build_symbol_metadata(self, symbol: str, quote_payload: dict[str, object]) -> NormalizedSymbolMetadata:
        return NormalizedSymbolMetadata(
            provider=MarketDataProvider.TRADIER,
            asset_class=AssetClass.STOCK,
            symbol=symbol,
            provider_symbol=symbol,
            base_currency=symbol,
            quote_currency="USD",
            tick_size=Decimal("0.01"),
            lot_size=Decimal("1"),
            is_active=quote_payload.get("type") == "stock",
            last_synced_at=datetime.now(UTC),
        )

    async def _get_json(self, path: str, params: dict[str, object] | None = None) -> dict[str, object]:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        if self._client is not None:
            response = await self._client.get(f"{self.base_url}{path}", params=params, headers=headers)
            response.raise_for_status()
            return response.json()

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{self.base_url}{path}", params=params, headers=headers)
            response.raise_for_status()
            return response.json()

    def _decimal_or_none(self, value: object) -> Decimal | None:
        if value is None:
            return None
        return Decimal(str(value))
