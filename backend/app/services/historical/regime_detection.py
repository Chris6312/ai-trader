from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from app.services.historical.regime_detection_schemas import RegimeDetectionRecord, RegimeDetectionSummary
from app.services.historical.sentiment_scoring_schemas import SentimentScoreRecord
from app.services.historical.technical_scoring_schemas import TechnicalScoreRecord

_DECIMAL_ZERO = Decimal("0")
_DECIMAL_ONE = Decimal("1")
_DECIMAL_TWO = Decimal("2")

_REQUIRED_TECHNICAL_COMPONENTS = {"trend", "momentum", "volume", "structure"}
_REQUIRED_SENTIMENT_COMPONENTS = {"news", "narrative", "sector", "macro"}


class RegimeDetectionService:
    DETECTION_VERSION = "11f_v1"
    SUPPORTED_TECHNICAL_SCORING_VERSIONS = {"11d_v1"}
    SUPPORTED_SENTIMENT_SCORING_VERSIONS = {"11e_v1"}

    def detect_regimes(
        self,
        technical_rows: Sequence[TechnicalScoreRecord],
        sentiment_rows: Sequence[SentimentScoreRecord],
    ) -> list[RegimeDetectionRecord]:
        technical_map = self._prepare_technical_rows(technical_rows)
        sentiment_map = self._prepare_sentiment_rows(sentiment_rows)
        self._validate_series_compatibility(technical_map, sentiment_map)

        shared_times = sorted(set(technical_map) & set(sentiment_map))
        return [self._classify_row(technical_map[candle_time], sentiment_map[candle_time]) for candle_time in shared_times]

    def detect_latest_regime(
        self,
        technical_rows: Sequence[TechnicalScoreRecord],
        sentiment_rows: Sequence[SentimentScoreRecord],
    ) -> RegimeDetectionRecord | None:
        rows = self.detect_regimes(technical_rows, sentiment_rows)
        if not rows:
            return None
        return rows[-1]

    def summarize(
        self,
        technical_rows: Sequence[TechnicalScoreRecord],
        sentiment_rows: Sequence[SentimentScoreRecord],
    ) -> RegimeDetectionSummary | None:
        technical_map = self._prepare_technical_rows(technical_rows)
        sentiment_map = self._prepare_sentiment_rows(sentiment_rows)
        if not technical_map or not sentiment_map:
            return None
        self._validate_series_compatibility(technical_map, sentiment_map)

        first = next(iter(technical_map.values()))
        shared_times = set(technical_map) & set(sentiment_map)
        return RegimeDetectionSummary(
            symbol=first.symbol,
            asset_class=first.asset_class,
            timeframe=first.timeframe,
            source_label=first.source_label,
            rows_technical_input=len(technical_map),
            rows_sentiment_input=len(sentiment_map),
            rows_classified=len(shared_times),
            detection_version=self.DETECTION_VERSION,
            technical_scoring_version=first.scoring_version,
            sentiment_scoring_version=next(iter(sentiment_map.values())).scoring_version,
        )

    def _prepare_technical_rows(self, rows: Sequence[TechnicalScoreRecord]) -> dict[object, TechnicalScoreRecord]:
        if not rows:
            return {}

        ordered = sorted(rows, key=lambda item: item.candle_time)
        first = ordered[0]
        prepared: dict[object, TechnicalScoreRecord] = {}
        for row in ordered:
            if row.symbol != first.symbol:
                raise ValueError("regime technical series must contain exactly one symbol")
            if row.asset_class != first.asset_class:
                raise ValueError("regime technical series must contain exactly one asset class")
            if row.timeframe != first.timeframe:
                raise ValueError("regime technical series must contain exactly one timeframe")
            if row.source_label != first.source_label:
                raise ValueError("regime technical series must contain exactly one source label")
            if row.scoring_version != first.scoring_version:
                raise ValueError("regime technical series must contain exactly one scoring version")
            if row.candle_time in prepared:
                raise ValueError("regime technical series cannot contain duplicate candle_time values")
            if row.scoring_version not in self.SUPPORTED_TECHNICAL_SCORING_VERSIONS:
                raise ValueError(f"unsupported technical scoring_version: {row.scoring_version}")
            missing = sorted(_REQUIRED_TECHNICAL_COMPONENTS - set(row.component_scores))
            if missing:
                raise ValueError(f"technical score row missing required components: {', '.join(missing)}")
            prepared[row.candle_time] = row
        return prepared

    def _prepare_sentiment_rows(self, rows: Sequence[SentimentScoreRecord]) -> dict[object, SentimentScoreRecord]:
        if not rows:
            return {}

        ordered = sorted(rows, key=lambda item: item.candle_time)
        first = ordered[0]
        prepared: dict[object, SentimentScoreRecord] = {}
        for row in ordered:
            if row.symbol != first.symbol:
                raise ValueError("regime sentiment series must contain exactly one symbol")
            if row.asset_class != first.asset_class:
                raise ValueError("regime sentiment series must contain exactly one asset class")
            if row.timeframe != first.timeframe:
                raise ValueError("regime sentiment series must contain exactly one timeframe")
            if row.source_label != first.source_label:
                raise ValueError("regime sentiment series must contain exactly one source label")
            if row.scoring_version != first.scoring_version:
                raise ValueError("regime sentiment series must contain exactly one scoring version")
            if row.candle_time in prepared:
                raise ValueError("regime sentiment series cannot contain duplicate candle_time values")
            if row.scoring_version not in self.SUPPORTED_SENTIMENT_SCORING_VERSIONS:
                raise ValueError(f"unsupported sentiment scoring_version: {row.scoring_version}")
            missing = sorted(_REQUIRED_SENTIMENT_COMPONENTS - set(row.component_scores))
            if missing:
                raise ValueError(f"sentiment score row missing required components: {', '.join(missing)}")
            prepared[row.candle_time] = row
        return prepared

    def _validate_series_compatibility(
        self,
        technical_map: dict[object, TechnicalScoreRecord],
        sentiment_map: dict[object, SentimentScoreRecord],
    ) -> None:
        if not technical_map or not sentiment_map:
            return

        technical_first = next(iter(technical_map.values()))
        sentiment_first = next(iter(sentiment_map.values()))
        if technical_first.symbol != sentiment_first.symbol:
            raise ValueError("regime technical and sentiment series must reference the same symbol")
        if technical_first.asset_class != sentiment_first.asset_class:
            raise ValueError("regime technical and sentiment series must reference the same asset class")
        if technical_first.timeframe != sentiment_first.timeframe:
            raise ValueError("regime technical and sentiment series must reference the same timeframe")
        if technical_first.source_label != sentiment_first.source_label:
            raise ValueError("regime technical and sentiment series must reference the same source label")

    def _classify_row(
        self,
        technical_row: TechnicalScoreRecord,
        sentiment_row: SentimentScoreRecord,
    ) -> RegimeDetectionRecord:
        trend = technical_row.component_scores["trend"]
        momentum = technical_row.component_scores["momentum"]
        volume = technical_row.component_scores["volume"]
        structure = technical_row.component_scores["structure"]
        news = sentiment_row.component_scores["news"]
        narrative = sentiment_row.component_scores["narrative"]
        sector = sentiment_row.component_scores["sector"]
        macro = sentiment_row.component_scores["macro"]

        trend_strength = self._mean([trend, momentum, structure])
        participation = self._mean([volume, narrative])
        macro_context = self._mean([news, sector, macro])
        regime_score = self._weighted_average(
            {
                "technical": Decimal("0.50"),
                "sentiment": Decimal("0.30"),
                "participation": Decimal("0.20"),
            },
            {
                "technical": technical_row.technical_score,
                "sentiment": sentiment_row.sentiment_score,
                "participation": participation,
            },
        )
        stability_score = self._weighted_average(
            {
                "trend_strength": Decimal("0.45"),
                "structure": Decimal("0.20"),
                "macro_context": Decimal("0.35"),
            },
            {
                "trend_strength": trend_strength,
                "structure": structure,
                "macro_context": macro_context,
            },
        )

        if regime_score >= Decimal("0.67") and stability_score >= Decimal("0.55"):
            regime_label = "risk_on"
        elif regime_score <= Decimal("0.40"):
            regime_label = "risk_off"
        else:
            regime_label = "neutral"

        component_scores = {
            "trend_strength": trend_strength,
            "participation": participation,
            "macro_context": macro_context,
            "stability": stability_score,
        }
        inputs = {
            "technical_score": technical_row.technical_score,
            "sentiment_score": sentiment_row.sentiment_score,
            "technical_trend": trend,
            "technical_momentum": momentum,
            "technical_volume": volume,
            "technical_structure": structure,
            "sentiment_news": news,
            "sentiment_narrative": narrative,
            "sentiment_sector": sector,
            "sentiment_macro": macro,
        }

        return RegimeDetectionRecord(
            symbol=technical_row.symbol,
            asset_class=technical_row.asset_class,
            timeframe=technical_row.timeframe,
            candle_time=technical_row.candle_time,
            source_label=technical_row.source_label,
            technical_scoring_version=technical_row.scoring_version,
            sentiment_scoring_version=sentiment_row.scoring_version,
            detection_version=self.DETECTION_VERSION,
            regime_label=regime_label,
            regime_score=regime_score,
            component_scores=component_scores,
            inputs=inputs,
        )

    def _weighted_average(self, weights: dict[str, Decimal], values: dict[str, Decimal]) -> Decimal:
        total_weight = sum(weights.values(), _DECIMAL_ZERO)
        if total_weight <= _DECIMAL_ZERO:
            return _DECIMAL_ZERO
        weighted_sum = sum(weights[name] * values[name] for name in weights)
        return weighted_sum / total_weight

    def _mean(self, values: Sequence[Decimal]) -> Decimal:
        if not values:
            return _DECIMAL_ZERO
        return sum(values, _DECIMAL_ZERO) / Decimal(len(values))
