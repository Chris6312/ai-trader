from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from app.services.historical.regime_detection_schemas import RegimeDetectionRecord
from app.services.historical.sentiment_scoring_schemas import SentimentScoreRecord
from app.services.historical.technical_scoring_schemas import TechnicalScoreRecord
from app.services.historical.universe_composer_schemas import UniverseCandidateRecord, UniverseCompositionSummary

_DECIMAL_ZERO = Decimal("0")

_REQUIRED_REGIME_COMPONENTS = {
    "trend_strength",
    "participation",
    "macro_context",
    "stability",
}


class UniverseComposerService:
    COMPOSITION_VERSION = "11g_v1"
    SUPPORTED_TECHNICAL_SCORING_VERSIONS = {"11d_v1"}
    SUPPORTED_SENTIMENT_SCORING_VERSIONS = {"11e_v1"}
    SUPPORTED_REGIME_DETECTION_VERSIONS = {"11f_v1"}

    def compose_universe(
        self,
        technical_rows: Sequence[TechnicalScoreRecord],
        sentiment_rows: Sequence[SentimentScoreRecord],
        regime_rows: Sequence[RegimeDetectionRecord],
        *,
        max_candidates: int = 8,
    ) -> list[UniverseCandidateRecord]:
        if max_candidates <= 0:
            raise ValueError("max_candidates must be positive")

        technical_map = self._prepare_technical_rows(technical_rows)
        sentiment_map = self._prepare_sentiment_rows(sentiment_rows)
        regime_map = self._prepare_regime_rows(regime_rows)
        self._validate_join_compatibility(technical_map, sentiment_map, regime_map)

        shared_keys = sorted(set(technical_map) & set(sentiment_map) & set(regime_map))
        eligible_rows: list[UniverseCandidateRecord] = []
        for key in shared_keys:
            candidate = self._compose_candidate(technical_map[key], sentiment_map[key], regime_map[key])
            if candidate.decision_label != "exclude":
                eligible_rows.append(candidate)

        ranked = sorted(
            eligible_rows,
            key=lambda row: (
                -row.universe_score,
                row.asset_class,
                row.symbol,
                row.timeframe,
                row.candle_time,
            ),
        )

        composed: list[UniverseCandidateRecord] = []
        for index, row in enumerate(ranked, start=1):
            composed.append(
                UniverseCandidateRecord(
                    symbol=row.symbol,
                    asset_class=row.asset_class,
                    timeframe=row.timeframe,
                    candle_time=row.candle_time,
                    source_label=row.source_label,
                    technical_scoring_version=row.technical_scoring_version,
                    sentiment_scoring_version=row.sentiment_scoring_version,
                    regime_detection_version=row.regime_detection_version,
                    composition_version=row.composition_version,
                    rank=index,
                    selected=index <= max_candidates,
                    universe_score=row.universe_score,
                    decision_label=row.decision_label,
                    component_scores=row.component_scores,
                    inputs=row.inputs,
                )
            )
        return composed

    def compose_top_universe(
        self,
        technical_rows: Sequence[TechnicalScoreRecord],
        sentiment_rows: Sequence[SentimentScoreRecord],
        regime_rows: Sequence[RegimeDetectionRecord],
        *,
        max_candidates: int = 8,
    ) -> list[UniverseCandidateRecord]:
        return [row for row in self.compose_universe(technical_rows, sentiment_rows, regime_rows, max_candidates=max_candidates) if row.selected]

    def summarize(
        self,
        technical_rows: Sequence[TechnicalScoreRecord],
        sentiment_rows: Sequence[SentimentScoreRecord],
        regime_rows: Sequence[RegimeDetectionRecord],
        *,
        max_candidates: int = 8,
    ) -> UniverseCompositionSummary:
        composed = self.compose_universe(
            technical_rows,
            sentiment_rows,
            regime_rows,
            max_candidates=max_candidates,
        )
        return UniverseCompositionSummary(
            rows_technical_input=len(technical_rows),
            rows_sentiment_input=len(sentiment_rows),
            rows_regime_input=len(regime_rows),
            rows_eligible=len(composed),
            rows_composed=len(composed),
            rows_selected=sum(1 for row in composed if row.selected),
            composition_version=self.COMPOSITION_VERSION,
            technical_scoring_version=composed[0].technical_scoring_version if composed else None,
            sentiment_scoring_version=composed[0].sentiment_scoring_version if composed else None,
            regime_detection_version=composed[0].regime_detection_version if composed else None,
        )

    def _prepare_technical_rows(self, rows: Sequence[TechnicalScoreRecord]) -> dict[tuple[str, str, str, object, str], TechnicalScoreRecord]:
        prepared: dict[tuple[str, str, str, object, str], TechnicalScoreRecord] = {}
        for row in rows:
            if row.scoring_version not in self.SUPPORTED_TECHNICAL_SCORING_VERSIONS:
                raise ValueError(f"unsupported technical scoring_version: {row.scoring_version}")
            key = (row.symbol, row.asset_class, row.timeframe, row.candle_time, row.source_label)
            if key in prepared:
                raise ValueError("technical universe rows cannot contain duplicate symbol/timeframe/candle/source combinations")
            prepared[key] = row
        return prepared

    def _prepare_sentiment_rows(self, rows: Sequence[SentimentScoreRecord]) -> dict[tuple[str, str, str, object, str], SentimentScoreRecord]:
        prepared: dict[tuple[str, str, str, object, str], SentimentScoreRecord] = {}
        for row in rows:
            if row.scoring_version not in self.SUPPORTED_SENTIMENT_SCORING_VERSIONS:
                raise ValueError(f"unsupported sentiment scoring_version: {row.scoring_version}")
            key = (row.symbol, row.asset_class, row.timeframe, row.candle_time, row.source_label)
            if key in prepared:
                raise ValueError("sentiment universe rows cannot contain duplicate symbol/timeframe/candle/source combinations")
            prepared[key] = row
        return prepared

    def _prepare_regime_rows(self, rows: Sequence[RegimeDetectionRecord]) -> dict[tuple[str, str, str, object, str], RegimeDetectionRecord]:
        prepared: dict[tuple[str, str, str, object, str], RegimeDetectionRecord] = {}
        for row in rows:
            if row.detection_version not in self.SUPPORTED_REGIME_DETECTION_VERSIONS:
                raise ValueError(f"unsupported regime detection_version: {row.detection_version}")
            missing = sorted(_REQUIRED_REGIME_COMPONENTS - set(row.component_scores))
            if missing:
                raise ValueError(f"regime detection row missing required components: {', '.join(missing)}")
            key = (row.symbol, row.asset_class, row.timeframe, row.candle_time, row.source_label)
            if key in prepared:
                raise ValueError("regime universe rows cannot contain duplicate symbol/timeframe/candle/source combinations")
            prepared[key] = row
        return prepared

    def _validate_join_compatibility(
        self,
        technical_map: dict[tuple[str, str, str, object, str], TechnicalScoreRecord],
        sentiment_map: dict[tuple[str, str, str, object, str], SentimentScoreRecord],
        regime_map: dict[tuple[str, str, str, object, str], RegimeDetectionRecord],
    ) -> None:
        shared_keys = set(technical_map) & set(sentiment_map) & set(regime_map)
        for key in shared_keys:
            technical_row = technical_map[key]
            sentiment_row = sentiment_map[key]
            regime_row = regime_map[key]
            if technical_row.symbol != sentiment_row.symbol or technical_row.symbol != regime_row.symbol:
                raise ValueError("universe rows must reference the same symbol")
            if technical_row.asset_class != sentiment_row.asset_class or technical_row.asset_class != regime_row.asset_class:
                raise ValueError("universe rows must reference the same asset class")
            if technical_row.timeframe != sentiment_row.timeframe or technical_row.timeframe != regime_row.timeframe:
                raise ValueError("universe rows must reference the same timeframe")
            if technical_row.source_label != sentiment_row.source_label or technical_row.source_label != regime_row.source_label:
                raise ValueError("universe rows must reference the same source label")

    def _compose_candidate(
        self,
        technical_row: TechnicalScoreRecord,
        sentiment_row: SentimentScoreRecord,
        regime_row: RegimeDetectionRecord,
    ) -> UniverseCandidateRecord:
        regime_strength = self._label_strength(regime_row.regime_label)
        stability = regime_row.component_scores["stability"]
        participation = regime_row.component_scores["participation"]
        conviction = self._weighted_average(
            {
                "technical": Decimal("0.45"),
                "sentiment": Decimal("0.20"),
                "regime": Decimal("0.25"),
                "stability": Decimal("0.10"),
            },
            {
                "technical": technical_row.technical_score,
                "sentiment": sentiment_row.sentiment_score,
                "regime": regime_row.regime_score,
                "stability": stability,
            },
        )
        universe_score = conviction * regime_strength

        if regime_row.regime_label == "risk_off" or regime_row.regime_score < Decimal("0.45"):
            decision_label = "exclude"
        elif universe_score >= Decimal("0.68") and participation >= Decimal("0.55"):
            decision_label = "include"
        else:
            decision_label = "watch"

        component_scores = {
            "technical": technical_row.technical_score,
            "sentiment": sentiment_row.sentiment_score,
            "regime": regime_row.regime_score,
            "stability": stability,
            "participation": participation,
            "conviction": conviction,
            "regime_strength": regime_strength,
        }
        inputs = {
            "technical_trend": technical_row.component_scores["trend"],
            "technical_momentum": technical_row.component_scores["momentum"],
            "technical_volume": technical_row.component_scores["volume"],
            "technical_structure": technical_row.component_scores["structure"],
            "sentiment_news": sentiment_row.component_scores["news"],
            "sentiment_narrative": sentiment_row.component_scores["narrative"],
            "sentiment_sector": sentiment_row.component_scores["sector"],
            "sentiment_macro": sentiment_row.component_scores["macro"],
            "regime_trend_strength": regime_row.component_scores["trend_strength"],
            "regime_macro_context": regime_row.component_scores["macro_context"],
        }

        return UniverseCandidateRecord(
            symbol=technical_row.symbol,
            asset_class=technical_row.asset_class,
            timeframe=technical_row.timeframe,
            candle_time=technical_row.candle_time,
            source_label=technical_row.source_label,
            technical_scoring_version=technical_row.scoring_version,
            sentiment_scoring_version=sentiment_row.scoring_version,
            regime_detection_version=regime_row.detection_version,
            composition_version=self.COMPOSITION_VERSION,
            rank=0,
            selected=False,
            universe_score=universe_score,
            decision_label=decision_label,
            component_scores=component_scores,
            inputs=inputs,
        )

    def _label_strength(self, label: str) -> Decimal:
        if label == "risk_on":
            return Decimal("1.00")
        if label == "neutral":
            return Decimal("0.82")
        if label == "risk_off":
            return Decimal("0.45")
        raise ValueError(f"unsupported regime label: {label}")

    def _weighted_average(self, weights: dict[str, Decimal], values: dict[str, Decimal]) -> Decimal:
        total_weight = sum(weights.values(), _DECIMAL_ZERO)
        if total_weight <= _DECIMAL_ZERO:
            return _DECIMAL_ZERO
        weighted_sum = sum(weights[name] * values[name] for name in weights)
        return weighted_sum / total_weight
