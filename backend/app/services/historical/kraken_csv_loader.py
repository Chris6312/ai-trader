from __future__ import annotations

import csv
import re
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from app.services.historical.retention import retention_bucket_for_timeframe
from app.services.historical.schemas import HistoricalCandleRecord


_TIMEFRAME_MINUTES: dict[str, int] = {
    "15m": 15,
    "1h": 60,
    "4h": 240,
    "1d": 1440,
}

_ALIAS_MAP: dict[str, str] = {
    "XBT": "BTC",
}


class KrakenCsvLoader:
    def discover_files(
        self,
        *,
        directory: Path,
        timeframe: str,
    ) -> list[Path]:
        _validate_timeframe(timeframe)
        if not directory.exists():
            return []

        suffixes = {
            "15m": ("15m", "15", "15min"),
            "1h": ("1h", "60", "60m"),
            "4h": ("4h", "240", "240m"),
            "1d": ("1d", "1440", "1440m", "daily"),
        }[timeframe]

        matches: list[Path] = []
        for path in sorted(directory.glob("*.csv")):
            stem_lower = path.stem.lower()
            if any(
                stem_lower.endswith(token.lower()) or f"_{token.lower()}_" in stem_lower
                for token in suffixes
            ):
                matches.append(path)
        return matches

    def load_directory(
        self,
        *,
        directory: Path,
        timeframe: str,
    ) -> list[HistoricalCandleRecord]:
        candles: list[HistoricalCandleRecord] = []
        for path in self.discover_files(directory=directory, timeframe=timeframe):
            candles.extend(self.load_file(path=path, timeframe=timeframe))
        return sorted(candles, key=lambda row: (row.symbol, row.candle_time))

    def load_file(
        self,
        *,
        path: Path,
        timeframe: str,
    ) -> list[HistoricalCandleRecord]:
        _validate_timeframe(timeframe)
        symbol = _symbol_from_filename(path)
        fetched_at = datetime.now(UTC)
        records: list[HistoricalCandleRecord] = []

        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            for row in reader:
                if not row or _looks_like_header(row):
                    continue
                record = _parse_row(
                    symbol=symbol,
                    timeframe=timeframe,
                    row=row,
                    fetched_at=fetched_at,
                )
                if record is not None:
                    records.append(record)

        return sorted(records, key=lambda row: row.candle_time)


def _validate_timeframe(timeframe: str) -> None:
    if timeframe not in _TIMEFRAME_MINUTES:
        raise ValueError(f"Unsupported timeframe: {timeframe}")


def _looks_like_header(row: list[str]) -> bool:
    joined = ",".join(cell.strip().lower() for cell in row)
    return "timestamp" in joined or "time" in joined or "open" in joined


def _parse_row(
    *,
    symbol: str,
    timeframe: str,
    row: list[str],
    fetched_at: datetime,
) -> HistoricalCandleRecord | None:
    if len(row) < 6:
        return None

    timestamp = _parse_timestamp(row[0])
    if timestamp is None:
        return None

    return HistoricalCandleRecord(
        symbol=symbol,
        asset_class="crypto",
        timeframe=timeframe,
        candle_time=timestamp,
        open=Decimal(str(row[1])),
        high=Decimal(str(row[2])),
        low=Decimal(str(row[3])),
        close=Decimal(str(row[4])),
        volume=Decimal(str(row[5])),
        source_label="kraken_csv",
        fetched_at=fetched_at,
        retention_bucket=retention_bucket_for_timeframe(timeframe),
    )


def _parse_timestamp(raw: str) -> datetime | None:
    value = raw.strip()
    if not value:
        return None

    try:
        if re.fullmatch(r"\d+", value):
            return datetime.fromtimestamp(int(value), tz=UTC)
        normalized = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except Exception:
        return None


def _symbol_from_filename(path: Path) -> str:
    stem = path.stem
    match = re.match(
        r"([A-Za-z0-9]+?)(?:[_-](?:15m|15|15min|1h|60|60m|4h|240|240m|1d|1440|1440m|daily))?$",
        stem,
        re.IGNORECASE,
    )
    pair_token = match.group(1) if match else stem
    return _normalize_pair_token(pair_token)


def _normalize_pair_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9]", "", value).upper()
    if len(token) < 6:
        raise ValueError(f"Unable to infer Kraken pair from filename: {value}")

    known_quotes = ("USDT", "USDC", "USD", "EUR", "BTC")
    quote = next((q for q in known_quotes if token.endswith(q)), None)
    if quote is None:
        quote = token[-3:]

    base = token[: -len(quote)]

    # Handle Kraken provider-style prefixes like XXBTZUSD, XETHZUSD
    if len(base) > 3 and base.startswith(("X", "Z")):
        trimmed = base[1:]
        if len(trimmed) >= 3:
            base = trimmed
    if len(quote) > 3 and quote.startswith(("X", "Z")):
        trimmed = quote[1:]
        if len(trimmed) >= 3:
            quote = trimmed

    base = _ALIAS_MAP.get(base, base)
    quote = _ALIAS_MAP.get(quote, quote)
    return f"{base}/{quote}"