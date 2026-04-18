from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from app.services.historical.sentiment_scoring_schemas import (
    SentimentInputRecord,
    SentimentScoreRecord,
    SentimentScoreSummary,
)

_DECIMAL_ZERO = Decimal("0")
_DECIMAL_ONE = Decimal("1")

_REQUIRED_SIGNAL_KEYS = {
    "news_polarity",
    "narrative_strength",
    "sector_tailwind",
    "macro_alignment",
}


class SentimentScoringService:
    SCORING_VERSION = "11e_v1"
    SUPPORTED_INPUT_VERSIONS = {"11e_input_v1"}

    def score_input_rows(self, rows: Sequence[SentimentInputRecord]) -> list[SentimentScoreRecord]:
        ordered = self._prepare_rows(rows)
        return [self._score_row(row) for row in ordered]

    def score_latest_input_row(
        self,
        rows: Sequence[SentimentInputRecord],
    ) -> SentimentScoreRecord | None:
        ordered = self._prepare_rows(rows)
        if not ordered:
            return None
        return self._score_row(ordered[-1])

    def summarize(self, rows: Sequence[SentimentInputRecord]) -> SentimentScoreSummary | None:
        ordered = self._prepare_rows(rows)
        if not ordered:
            return None

        first = ordered[0]
        return SentimentScoreSummary(
            symbol=first.symbol,
            asset_class=first.asset_class,
            timeframe=first.timeframe,
            source_label=first.source_label,
            rows_input=len(ordered),
            rows_scored=len(ordered),
            scoring_version=self.SCORING_VERSION,
            input_version=first.input_version,
        )

    def _prepare_rows(self, rows: Sequence[SentimentInputRecord]) -> list[SentimentInputRecord]:
        if not rows:
            return []

        ordered = sorted(rows, key=lambda item: item.candle_time)
        first = ordered[0]
        seen_times: set = set()
        for row in ordered:
            if row.symbol != first.symbol:
                raise ValueError("sentiment score series must contain exactly one symbol")
            if row.asset_class != first.asset_class:
                raise ValueError("sentiment score series must contain exactly one asset class")
            if row.timeframe != first.timeframe:
                raise ValueError("sentiment score series must contain exactly one timeframe")
            if row.source_label != first.source_label:
                raise ValueError("sentiment score series must contain exactly one source label")
            if row.input_version != first.input_version:
                raise ValueError("sentiment score series must contain exactly one input version")
            if row.candle_time in seen_times:
                raise ValueError("sentiment score series cannot contain duplicate candle_time values")
            if row.input_version not in self.SUPPORTED_INPUT_VERSIONS:
                raise ValueError(f"unsupported input_version: {row.input_version}")
            missing = sorted(_REQUIRED_SIGNAL_KEYS - set(row.signals))
            if missing:
                raise ValueError(f"sentiment input row missing required keys: {', '.join(missing)}")
            seen_times.add(row.candle_time)
        return ordered

    def _score_row(self, row: SentimentInputRecord) -> SentimentScoreRecord:
        signals = row.signals

        component_scores = {
            "news": self._normalize_signed(signals["news_polarity"]),
            "narrative": self._clamp(signals["narrative_strength"]),
            "sector": self._clamp(signals["sector_tailwind"]),
            "macro": self._clamp(signals["macro_alignment"]),
        }

        sentiment_score = self._weighted_average(
            {
                "news": Decimal("0.35"),
                "narrative": Decimal("0.30"),
                "sector": Decimal("0.20"),
                "macro": Decimal("0.15"),
            },
            component_scores,
        )

        return SentimentScoreRecord(
            symbol=row.symbol,
            asset_class=row.asset_class,
            timeframe=row.timeframe,
            candle_time=row.candle_time,
            source_label=row.source_label,
            input_version=row.input_version,
            scoring_version=self.SCORING_VERSION,
            sentiment_score=sentiment_score,
            component_scores=component_scores,
            inputs={key: signals[key] for key in sorted(_REQUIRED_SIGNAL_KEYS)},
        )

    def _normalize_signed(self, value: Decimal) -> Decimal:
        normalized = (value + _DECIMAL_ONE) / Decimal("2")
        return self._clamp(normalized)

    def _weighted_average(self, weights: dict[str, Decimal], values: dict[str, Decimal]) -> Decimal:
        total_weight = sum(weights.values(), _DECIMAL_ZERO)
        if total_weight <= _DECIMAL_ZERO:
            return _DECIMAL_ZERO
        weighted_sum = sum(weights[name] * values[name] for name in weights)
        return weighted_sum / total_weight

    def _clamp(self, value: Decimal) -> Decimal:
        if value < _DECIMAL_ZERO:
            return _DECIMAL_ZERO
        if value > _DECIMAL_ONE:
            return _DECIMAL_ONE
        return value
