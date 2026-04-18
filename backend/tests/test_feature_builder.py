from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.services.historical.feature_builder import FeatureBuilderService
from app.services.historical.schemas import HistoricalCandleRecord


def _build_candles(*, symbol: str = "AAPL", asset_class: str = "stock") -> list[HistoricalCandleRecord]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles: list[HistoricalCandleRecord] = []
    for index in range(25):
        close = Decimal(100 + index)
        candles.append(
            HistoricalCandleRecord(
                symbol=symbol,
                asset_class=asset_class,
                timeframe="1h",
                candle_time=start + timedelta(hours=index),
                open=close - Decimal("1"),
                high=close + Decimal("1"),
                low=close - Decimal("2"),
                close=close,
                volume=Decimal(100 + index * 10),
                source_label="alpaca" if asset_class == "stock" else "kraken_csv",
                fetched_at=start + timedelta(days=1),
                retention_bucket="intraday_medium",
            )
        )
    return candles


def test_build_feature_rows_returns_expected_latest_metrics() -> None:
    service = FeatureBuilderService()
    rows = service.build_feature_rows(_build_candles())

    assert len(rows) == 6
    latest = rows[-1]

    assert latest.symbol == "AAPL"
    assert latest.feature_version == "11c_v1"
    assert latest.values["volume_ratio_5"] == Decimal("1.0625")
    assert latest.values["range_position_20"] == Decimal("0.9545454545454545454545454545")
    assert latest.values["close_vs_sma_5"] == Decimal("0.01639344262295081967213114754")
    assert latest.values["return_1"] == Decimal("0.008130081300813008130081300813")
    assert latest.values["realized_volatility_5"] > Decimal("0")


def test_build_latest_feature_row_supports_crypto_series() -> None:
    service = FeatureBuilderService()
    latest = service.build_latest_feature_row(_build_candles(symbol="BTC/USD", asset_class="crypto"))

    assert latest is not None
    assert latest.symbol == "BTC/USD"
    assert latest.asset_class == "crypto"
    assert latest.source_label == "kraken_csv"
    assert "close_vs_sma_20" in latest.values


def test_build_feature_rows_requires_consistent_series_metadata() -> None:
    service = FeatureBuilderService()
    candles = _build_candles()
    candles[-1] = HistoricalCandleRecord(
        symbol="MSFT",
        asset_class=candles[-1].asset_class,
        timeframe=candles[-1].timeframe,
        candle_time=candles[-1].candle_time,
        open=candles[-1].open,
        high=candles[-1].high,
        low=candles[-1].low,
        close=candles[-1].close,
        volume=candles[-1].volume,
        source_label=candles[-1].source_label,
        fetched_at=candles[-1].fetched_at,
        retention_bucket=candles[-1].retention_bucket,
    )

    try:
        service.build_feature_rows(candles)
    except ValueError as exc:
        assert str(exc) == "feature series must contain exactly one symbol"
    else:
        raise AssertionError("expected ValueError for mixed-series metadata")


def test_summarize_reports_warmup_and_output_counts() -> None:
    service = FeatureBuilderService()
    summary = service.summarize(_build_candles())

    assert summary is not None
    assert summary.rows_input == 25
    assert summary.rows_output == 6
    assert summary.warmup_rows_skipped == 19
    assert summary.feature_version == "11c_v1"
