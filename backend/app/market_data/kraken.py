from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import httpx

from app.market_data.schemas import NormalizedCandle, NormalizedQuote, NormalizedSymbolMetadata
from app.models import AssetClass, CandleInterval, MarketDataProvider


_INTERVAL_MINUTES_BY_VALUE = {
    CandleInterval.MINUTE_1: 1,
    CandleInterval.MINUTE_5: 5,
    CandleInterval.MINUTE_15: 15,
    CandleInterval.HOUR_1: 60,
    CandleInterval.HOUR_4: 240,
    CandleInterval.DAY_1: 1440,
}


class KrakenMarketDataAdapter:
    def __init__(
        self,
        base_url: str = "https://api.kraken.com/0/public",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = client

    async def fetch_ohlc(self, provider_symbol: str, interval: CandleInterval) -> list[NormalizedCandle]:
        params = {"pair": provider_symbol, "interval": _INTERVAL_MINUTES_BY_VALUE[interval]}
        payload = await self._get_json("/OHLC", params=params)
        return self.parse_ohlc_response(provider_symbol=provider_symbol, interval=interval, payload=payload)

    async def fetch_ticker(self, provider_symbol: str) -> NormalizedQuote:
        payload = await self._get_json("/Ticker", params={"pair": provider_symbol})
        return self.parse_ticker_response(provider_symbol=provider_symbol, payload=payload)

    async def fetch_asset_pairs(self) -> list[NormalizedSymbolMetadata]:
        payload = await self._get_json("/AssetPairs")
        result = payload.get("result", {})
        return [
            self.parse_asset_pair_response(provider_symbol=provider_symbol, payload=item)
            for provider_symbol, item in result.items()
            if isinstance(item, dict)
        ]

    async def _get_json(self, path: str, params: dict[str, object] | None = None) -> dict[str, object]:
        if self._client is not None:
            response = await self._client.get(f"{self.base_url}{path}", params=params)
            response.raise_for_status()
            return response.json()

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{self.base_url}{path}", params=params)
            response.raise_for_status()
            return response.json()

    def parse_ohlc_response(
        self,
        provider_symbol: str,
        interval: CandleInterval,
        payload: dict[str, object],
    ) -> list[NormalizedCandle]:
        result = payload.get("result", {})
        rows = result.get(provider_symbol, []) if isinstance(result, dict) else []
        normalized_symbol = self._normalize_symbol(provider_symbol)
        candles: list[NormalizedCandle] = []

        for row in rows:
            if not isinstance(row, list) or len(row) < 8:
                continue

            open_time = datetime.fromtimestamp(int(row[0]), tz=UTC)
            close_time = self._compute_close_time(open_time=open_time, interval=interval)
            candles.append(
                NormalizedCandle(
                    provider=MarketDataProvider.KRAKEN,
                    asset_class=AssetClass.CRYPTO,
                    symbol=normalized_symbol,
                    interval=interval,
                    open_time=open_time,
                    close_time=close_time,
                    open_price=Decimal(str(row[1])),
                    high_price=Decimal(str(row[2])),
                    low_price=Decimal(str(row[3])),
                    close_price=Decimal(str(row[4])),
                    vwap=Decimal(str(row[5])),
                    volume=Decimal(str(row[6])),
                    trade_count=int(row[7]),
                    is_closed=True,
                    source_updated_at=datetime.now(UTC),
                )
            )

        return candles

    def parse_ticker_response(self, provider_symbol: str, payload: dict[str, object]) -> NormalizedQuote:
        result = payload.get("result", {})
        ticker = result.get(provider_symbol, {}) if isinstance(result, dict) else {}
        bid = self._first_decimal(ticker.get("b"))
        ask = self._first_decimal(ticker.get("a"))
        last = self._first_decimal(ticker.get("c")) or Decimal("0")
        volume_24h = self._second_decimal(ticker.get("v"))
        mark = last if bid is None or ask is None else (bid + ask) / Decimal("2")

        return NormalizedQuote(
            provider=MarketDataProvider.KRAKEN,
            asset_class=AssetClass.CRYPTO,
            symbol=self._normalize_symbol(provider_symbol),
            bid=bid,
            ask=ask,
            last=last,
            mark=mark,
            volume_24h=volume_24h,
            as_of=datetime.now(UTC),
        )

    def parse_asset_pair_response(
        self,
        provider_symbol: str,
        payload: dict[str, object],
    ) -> NormalizedSymbolMetadata:
        wsname = str(payload.get("wsname") or provider_symbol)
        base_currency, quote_currency = self._split_wsname(wsname)

        return NormalizedSymbolMetadata(
            provider=MarketDataProvider.KRAKEN,
            asset_class=AssetClass.CRYPTO,
            symbol=wsname,
            provider_symbol=provider_symbol,
            base_currency=base_currency,
            quote_currency=quote_currency,
            tick_size=self._decimal_or_none(payload.get("tick_size")),
            lot_size=self._decimal_or_none(payload.get("lot_decimals")),
            is_active=payload.get("status", "online") == "online",
            last_synced_at=datetime.now(UTC),
        )

    def _normalize_symbol(self, provider_symbol: str) -> str:
        if "/" in provider_symbol:
            return provider_symbol
        if provider_symbol.endswith("USD") and len(provider_symbol) > 3:
            return f"{provider_symbol[:-3]}/USD"
        return provider_symbol

    def _split_wsname(self, wsname: str) -> tuple[str, str]:
        if "/" in wsname:
            return tuple(wsname.split("/", maxsplit=1))
        normalized = self._normalize_symbol(wsname)
        if "/" in normalized:
            return tuple(normalized.split("/", maxsplit=1))
        return normalized, "USD"

    def _compute_close_time(self, open_time: datetime, interval: CandleInterval) -> datetime:
        interval_minutes = _INTERVAL_MINUTES_BY_VALUE[interval]
        return open_time.fromtimestamp(open_time.timestamp() + (interval_minutes * 60), tz=UTC)

    def _decimal_or_none(self, value: object) -> Decimal | None:
        if value is None:
            return None
        return Decimal(str(value))

    def _first_decimal(self, value: object) -> Decimal | None:
        if isinstance(value, list) and value:
            return Decimal(str(value[0]))
        return None

    def _second_decimal(self, value: object) -> Decimal | None:
        if isinstance(value, list) and len(value) > 1:
            return Decimal(str(value[1]))
        return None
