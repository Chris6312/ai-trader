from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal, localcontext

from app.services.historical.feature_schemas import FeatureBuildSummary, HistoricalFeatureRecord
from app.services.historical.schemas import HistoricalCandleRecord


_DECIMAL_ZERO = Decimal("0")
_DECIMAL_ONE = Decimal("1")
_DECIMAL_HALF = Decimal("0.5")


class FeatureBuilderService:
    FEATURE_VERSION = "11c_v1"

    def __init__(
        self,
        *,
        short_window: int = 5,
        medium_window: int = 10,
        long_window: int = 20,
    ) -> None:
        if short_window <= 1:
            raise ValueError("short_window must be greater than 1")
        if medium_window < short_window:
            raise ValueError("medium_window must be greater than or equal to short_window")
        if long_window < medium_window:
            raise ValueError("long_window must be greater than or equal to medium_window")
        self.short_window = short_window
        self.medium_window = medium_window
        self.long_window = long_window

    @property
    def warmup_period(self) -> int:
        return self.long_window

    def build_feature_rows(self, candles: Sequence[HistoricalCandleRecord]) -> list[HistoricalFeatureRecord]:
        ordered = self._prepare_series(candles)
        if len(ordered) < self.warmup_period:
            return []

        rows: list[HistoricalFeatureRecord] = []
        for index in range(self.warmup_period - 1, len(ordered)):
            rows.append(self._build_row(ordered, index))
        return rows

    def build_latest_feature_row(
        self,
        candles: Sequence[HistoricalCandleRecord],
    ) -> HistoricalFeatureRecord | None:
        rows = self.build_feature_rows(candles)
        if not rows:
            return None
        return rows[-1]

    def summarize(self, candles: Sequence[HistoricalCandleRecord]) -> FeatureBuildSummary | None:
        ordered = self._prepare_series(candles)
        if not ordered:
            return None

        rows_output = max(0, len(ordered) - self.warmup_period + 1)
        first = ordered[0]
        return FeatureBuildSummary(
            symbol=first.symbol,
            asset_class=first.asset_class,
            timeframe=first.timeframe,
            source_label=first.source_label,
            rows_input=len(ordered),
            rows_output=rows_output,
            warmup_rows_skipped=min(len(ordered), self.warmup_period - 1),
            feature_version=self.FEATURE_VERSION,
        )

    def _prepare_series(self, candles: Sequence[HistoricalCandleRecord]) -> list[HistoricalCandleRecord]:
        if not candles:
            return []

        ordered = sorted(candles, key=lambda item: item.candle_time)
        first = ordered[0]
        seen_times: set = set()
        for candle in ordered:
            if candle.symbol != first.symbol:
                raise ValueError("feature series must contain exactly one symbol")
            if candle.asset_class != first.asset_class:
                raise ValueError("feature series must contain exactly one asset class")
            if candle.timeframe != first.timeframe:
                raise ValueError("feature series must contain exactly one timeframe")
            if candle.source_label != first.source_label:
                raise ValueError("feature series must contain exactly one source label")
            if candle.candle_time in seen_times:
                raise ValueError("feature series cannot contain duplicate candle_time values")
            seen_times.add(candle.candle_time)
        return ordered

    def _build_row(
        self,
        candles: Sequence[HistoricalCandleRecord],
        index: int,
    ) -> HistoricalFeatureRecord:
        current = candles[index]
        short_slice = candles[index - self.short_window + 1 : index + 1]
        medium_slice = candles[index - self.medium_window + 1 : index + 1]
        long_slice = candles[index - self.long_window + 1 : index + 1]

        closes_short = [candle.close for candle in short_slice]
        closes_medium = [candle.close for candle in medium_slice]
        closes_long = [candle.close for candle in long_slice]
        volumes_short = [candle.volume for candle in short_slice]
        volumes_medium = [candle.volume for candle in medium_slice]
        closes_returns_short = self._sequential_returns(closes_short)
        closes_returns_medium = self._sequential_returns(closes_medium)

        sma_short = self._mean(closes_short)
        sma_medium = self._mean(closes_medium)
        sma_long = self._mean(closes_long)
        avg_volume_short = self._mean(volumes_short)
        avg_volume_medium = self._mean(volumes_medium)
        long_low = min(candle.low for candle in long_slice)
        long_high = max(candle.high for candle in long_slice)

        values = {
            "bar_range_pct": self._pct_change(current.high, current.low),
            "body_pct": self._pct_change(current.close, current.open),
            "return_1": self._pct_change(current.close, candles[index - 1].close),
            "return_3": self._pct_change(current.close, candles[index - 3].close),
            "return_5": self._pct_change(current.close, candles[index - 5].close),
            "return_10": self._pct_change(current.close, candles[index - 10].close),
            "volume_ratio_5": self._safe_ratio(current.volume, avg_volume_short),
            "volume_ratio_10": self._safe_ratio(current.volume, avg_volume_medium),
            "avg_range_pct_5": self._mean([self._pct_change(candle.high, candle.low) for candle in short_slice]),
            "avg_range_pct_10": self._mean([self._pct_change(candle.high, candle.low) for candle in medium_slice]),
            "realized_volatility_5": self._stddev(closes_returns_short),
            "realized_volatility_10": self._stddev(closes_returns_medium),
            "close_vs_sma_5": self._pct_change(current.close, sma_short),
            "close_vs_sma_10": self._pct_change(current.close, sma_medium),
            "close_vs_sma_20": self._pct_change(current.close, sma_long),
            "sma_5_vs_sma_20": self._pct_change(sma_short, sma_long),
            "range_position_20": self._range_position(current.close, long_low, long_high),
        }

        return HistoricalFeatureRecord(
            symbol=current.symbol,
            asset_class=current.asset_class,
            timeframe=current.timeframe,
            candle_time=current.candle_time,
            source_label=current.source_label,
            feature_version=self.FEATURE_VERSION,
            values=values,
        )

    def _sequential_returns(self, values: Sequence[Decimal]) -> list[Decimal]:
        returns: list[Decimal] = []
        for index in range(1, len(values)):
            returns.append(self._pct_change(values[index], values[index - 1]))
        return returns

    def _mean(self, values: Sequence[Decimal]) -> Decimal:
        if not values:
            return _DECIMAL_ZERO
        return sum(values, _DECIMAL_ZERO) / Decimal(len(values))

    def _stddev(self, values: Sequence[Decimal]) -> Decimal:
        if not values:
            return _DECIMAL_ZERO
        mean_value = self._mean(values)
        variance = sum(
            (value - mean_value) * (value - mean_value)
            for value in values
        ) / Decimal(len(values))
        if variance <= _DECIMAL_ZERO:
            return _DECIMAL_ZERO
        with localcontext() as ctx:
            ctx.prec = 28
            return variance.sqrt()

    def _pct_change(self, current: Decimal, base: Decimal) -> Decimal:
        if base == _DECIMAL_ZERO:
            return _DECIMAL_ZERO
        return (current - base) / base

    def _safe_ratio(self, numerator: Decimal, denominator: Decimal) -> Decimal:
        if denominator == _DECIMAL_ZERO:
            return _DECIMAL_ZERO
        return numerator / denominator

    def _range_position(self, close: Decimal, low: Decimal, high: Decimal) -> Decimal:
        width = high - low
        if width <= _DECIMAL_ZERO:
            return _DECIMAL_HALF
        return (close - low) / width
