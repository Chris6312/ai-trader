from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from app.services.historical.feature_schemas import HistoricalFeatureRecord
from app.services.historical.technical_scoring_schemas import TechnicalScoreRecord, TechnicalScoreSummary

_DECIMAL_ZERO = Decimal("0")
_DECIMAL_ONE = Decimal("1")
_DECIMAL_TWO = Decimal("2")

_REQUIRED_FEATURE_KEYS = {
    "close_vs_sma_5",
    "close_vs_sma_20",
    "sma_5_vs_sma_20",
    "return_3",
    "return_5",
    "return_10",
    "volume_ratio_5",
    "volume_ratio_10",
    "range_position_20",
    "body_pct",
}


class TechnicalScoringService:
    SCORING_VERSION = "11d_v1"
    SUPPORTED_FEATURE_VERSIONS = {"11c_v1"}

    def score_feature_rows(self, rows: Sequence[HistoricalFeatureRecord]) -> list[TechnicalScoreRecord]:
        ordered = self._prepare_rows(rows)
        return [self._score_row(row) for row in ordered]

    def score_latest_feature_row(
        self,
        rows: Sequence[HistoricalFeatureRecord],
    ) -> TechnicalScoreRecord | None:
        ordered = self._prepare_rows(rows)
        if not ordered:
            return None
        return self._score_row(ordered[-1])

    def summarize(self, rows: Sequence[HistoricalFeatureRecord]) -> TechnicalScoreSummary | None:
        ordered = self._prepare_rows(rows)
        if not ordered:
            return None

        first = ordered[0]
        return TechnicalScoreSummary(
            symbol=first.symbol,
            asset_class=first.asset_class,
            timeframe=first.timeframe,
            source_label=first.source_label,
            rows_input=len(ordered),
            rows_scored=len(ordered),
            scoring_version=self.SCORING_VERSION,
            feature_version=first.feature_version,
        )

    def _prepare_rows(self, rows: Sequence[HistoricalFeatureRecord]) -> list[HistoricalFeatureRecord]:
        if not rows:
            return []

        ordered = sorted(rows, key=lambda item: item.candle_time)
        first = ordered[0]
        seen_times: set = set()
        for row in ordered:
            if row.symbol != first.symbol:
                raise ValueError("technical score series must contain exactly one symbol")
            if row.asset_class != first.asset_class:
                raise ValueError("technical score series must contain exactly one asset class")
            if row.timeframe != first.timeframe:
                raise ValueError("technical score series must contain exactly one timeframe")
            if row.source_label != first.source_label:
                raise ValueError("technical score series must contain exactly one source label")
            if row.feature_version != first.feature_version:
                raise ValueError("technical score series must contain exactly one feature version")
            if row.candle_time in seen_times:
                raise ValueError("technical score series cannot contain duplicate candle_time values")
            if row.feature_version not in self.SUPPORTED_FEATURE_VERSIONS:
                raise ValueError(f"unsupported feature_version: {row.feature_version}")
            missing = sorted(_REQUIRED_FEATURE_KEYS - set(row.values))
            if missing:
                raise ValueError(f"feature row missing required keys: {', '.join(missing)}")
            seen_times.add(row.candle_time)
        return ordered

    def _score_row(self, row: HistoricalFeatureRecord) -> TechnicalScoreRecord:
        values = row.values

        trend_score = self._mean(
            [
                self._normalize_signed(values["close_vs_sma_5"], Decimal("0.03")),
                self._normalize_signed(values["close_vs_sma_20"], Decimal("0.08")),
                self._normalize_signed(values["sma_5_vs_sma_20"], Decimal("0.06")),
            ]
        )
        momentum_score = self._mean(
            [
                self._normalize_signed(values["return_3"], Decimal("0.03")),
                self._normalize_signed(values["return_5"], Decimal("0.05")),
                self._normalize_signed(values["return_10"], Decimal("0.08")),
            ]
        )
        volume_score = self._mean(
            [
                self._normalize_band(values["volume_ratio_5"], Decimal("0.80"), Decimal("1.80")),
                self._normalize_band(values["volume_ratio_10"], Decimal("0.80"), Decimal("1.80")),
            ]
        )
        structure_score = self._mean(
            [
                self._normalize_band(values["range_position_20"], Decimal("0.35"), Decimal("1.00")),
                self._normalize_signed(values["body_pct"], Decimal("0.02")),
            ]
        )

        component_scores = {
            "trend": trend_score,
            "momentum": momentum_score,
            "volume": volume_score,
            "structure": structure_score,
        }

        technical_score = self._weighted_average(
            {
                "trend": Decimal("0.40"),
                "momentum": Decimal("0.25"),
                "volume": Decimal("0.20"),
                "structure": Decimal("0.15"),
            },
            component_scores,
        )

        return TechnicalScoreRecord(
            symbol=row.symbol,
            asset_class=row.asset_class,
            timeframe=row.timeframe,
            candle_time=row.candle_time,
            source_label=row.source_label,
            feature_version=row.feature_version,
            scoring_version=self.SCORING_VERSION,
            technical_score=technical_score,
            component_scores=component_scores,
            inputs={key: values[key] for key in sorted(_REQUIRED_FEATURE_KEYS)},
        )

    def _normalize_signed(self, value: Decimal, scale: Decimal) -> Decimal:
        if scale <= _DECIMAL_ZERO:
            raise ValueError("scale must be positive")
        centered = (value / scale + _DECIMAL_ONE) / _DECIMAL_TWO
        return self._clamp(centered)

    def _normalize_band(self, value: Decimal, lower: Decimal, upper: Decimal) -> Decimal:
        if upper <= lower:
            raise ValueError("upper must be greater than lower")
        normalized = (value - lower) / (upper - lower)
        return self._clamp(normalized)

    def _weighted_average(self, weights: dict[str, Decimal], values: dict[str, Decimal]) -> Decimal:
        total_weight = sum(weights.values(), _DECIMAL_ZERO)
        if total_weight <= _DECIMAL_ZERO:
            return _DECIMAL_ZERO
        weighted_sum = sum(
            weights[name] * values[name]
            for name in weights
        )
        return weighted_sum / total_weight

    def _mean(self, values: Sequence[Decimal]) -> Decimal:
        if not values:
            return _DECIMAL_ZERO
        return sum(values, _DECIMAL_ZERO) / Decimal(len(values))

    def _clamp(self, value: Decimal) -> Decimal:
        if value < _DECIMAL_ZERO:
            return _DECIMAL_ZERO
        if value > _DECIMAL_ONE:
            return _DECIMAL_ONE
        return value
