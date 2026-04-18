from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.services.historical.regime_detection_schemas import RegimeDetectionRecord
from app.services.historical.sentiment_scoring_schemas import SentimentScoreRecord
from app.services.historical.technical_scoring_schemas import TechnicalScoreRecord
from app.services.historical.universe_composer import UniverseComposerService


def _build_technical_row(
    *,
    symbol: str,
    asset_class: str,
    candle_time: datetime,
    score: str,
    trend: str,
    momentum: str,
    volume: str,
    structure: str,
) -> TechnicalScoreRecord:
    return TechnicalScoreRecord(
        symbol=symbol,
        asset_class=asset_class,
        timeframe="1h",
        candle_time=candle_time,
        source_label="alpaca" if asset_class == "stock" else "kraken_csv",
        feature_version="11c_v1",
        scoring_version="11d_v1",
        technical_score=Decimal(score),
        component_scores={
            "trend": Decimal(trend),
            "momentum": Decimal(momentum),
            "volume": Decimal(volume),
            "structure": Decimal(structure),
        },
        inputs={},
    )


def _build_sentiment_row(
    *,
    symbol: str,
    asset_class: str,
    candle_time: datetime,
    score: str,
    news: str,
    narrative: str,
    sector: str,
    macro: str,
) -> SentimentScoreRecord:
    return SentimentScoreRecord(
        symbol=symbol,
        asset_class=asset_class,
        timeframe="1h",
        candle_time=candle_time,
        source_label="alpaca" if asset_class == "stock" else "kraken_csv",
        input_version="11e_input_v1",
        scoring_version="11e_v1",
        sentiment_score=Decimal(score),
        component_scores={
            "news": Decimal(news),
            "narrative": Decimal(narrative),
            "sector": Decimal(sector),
            "macro": Decimal(macro),
        },
        inputs={},
    )


def _build_regime_row(
    *,
    symbol: str,
    asset_class: str,
    candle_time: datetime,
    label: str,
    regime_score: str,
    trend_strength: str,
    participation: str,
    macro_context: str,
    stability: str,
) -> RegimeDetectionRecord:
    return RegimeDetectionRecord(
        symbol=symbol,
        asset_class=asset_class,
        timeframe="1h",
        candle_time=candle_time,
        source_label="alpaca" if asset_class == "stock" else "kraken_csv",
        technical_scoring_version="11d_v1",
        sentiment_scoring_version="11e_v1",
        detection_version="11f_v1",
        regime_label=label,
        regime_score=Decimal(regime_score),
        component_scores={
            "trend_strength": Decimal(trend_strength),
            "participation": Decimal(participation),
            "macro_context": Decimal(macro_context),
            "stability": Decimal(stability),
        },
        inputs={},
    )


def test_compose_universe_ranks_multi_asset_candidates_and_filters_risk_off() -> None:
    service = UniverseComposerService()
    candle_time = datetime(2026, 1, 20, 15, tzinfo=UTC)

    technical_rows = [
        _build_technical_row(symbol="AAPL", asset_class="stock", candle_time=candle_time, score="0.79", trend="0.82", momentum="0.77", volume="0.69", structure="0.74"),
        _build_technical_row(symbol="BTC/USD", asset_class="crypto", candle_time=candle_time, score="0.88", trend="0.90", momentum="0.86", volume="0.79", structure="0.84"),
        _build_technical_row(symbol="TSLA", asset_class="stock", candle_time=candle_time, score="0.42", trend="0.43", momentum="0.40", volume="0.38", structure="0.46"),
    ]
    sentiment_rows = [
        _build_sentiment_row(symbol="AAPL", asset_class="stock", candle_time=candle_time, score="0.73", news="0.71", narrative="0.74", sector="0.72", macro="0.75"),
        _build_sentiment_row(symbol="BTC/USD", asset_class="crypto", candle_time=candle_time, score="0.67", news="0.62", narrative="0.70", sector="0.65", macro="0.71"),
        _build_sentiment_row(symbol="TSLA", asset_class="stock", candle_time=candle_time, score="0.39", news="0.36", narrative="0.42", sector="0.41", macro="0.37"),
    ]
    regime_rows = [
        _build_regime_row(symbol="AAPL", asset_class="stock", candle_time=candle_time, label="risk_on", regime_score="0.78", trend_strength="0.80", participation="0.66", macro_context="0.72", stability="0.74"),
        _build_regime_row(symbol="BTC/USD", asset_class="crypto", candle_time=candle_time, label="risk_on", regime_score="0.84", trend_strength="0.86", participation="0.72", macro_context="0.68", stability="0.77"),
        _build_regime_row(symbol="TSLA", asset_class="stock", candle_time=candle_time, label="risk_off", regime_score="0.34", trend_strength="0.38", participation="0.35", macro_context="0.33", stability="0.36"),
    ]

    composed = service.compose_universe(technical_rows, sentiment_rows, regime_rows, max_candidates=1)

    assert [row.symbol for row in composed] == ["BTC/USD", "AAPL"]
    assert composed[0].rank == 1
    assert composed[0].selected is True
    assert composed[0].decision_label == "include"
    assert composed[1].rank == 2
    assert composed[1].selected is False
    assert composed[1].decision_label == "include"
    assert all(row.symbol != "TSLA" for row in composed)


def test_compose_universe_marks_neutral_candidate_as_watch() -> None:
    service = UniverseComposerService()
    candle_time = datetime(2026, 1, 20, 16, tzinfo=UTC)

    composed = service.compose_universe(
        [
            _build_technical_row(symbol="MSFT", asset_class="stock", candle_time=candle_time, score="0.62", trend="0.65", momentum="0.59", volume="0.55", structure="0.63"),
        ],
        [
            _build_sentiment_row(symbol="MSFT", asset_class="stock", candle_time=candle_time, score="0.58", news="0.57", narrative="0.61", sector="0.56", macro="0.58"),
        ],
        [
            _build_regime_row(symbol="MSFT", asset_class="stock", candle_time=candle_time, label="neutral", regime_score="0.60", trend_strength="0.62", participation="0.53", macro_context="0.57", stability="0.59"),
        ],
        max_candidates=5,
    )

    assert len(composed) == 1
    assert composed[0].decision_label == "watch"
    assert composed[0].selected is True
    assert composed[0].component_scores["regime_strength"] == Decimal("0.82")


def test_compose_universe_requires_supported_regime_version() -> None:
    service = UniverseComposerService()
    candle_time = datetime(2026, 1, 20, 17, tzinfo=UTC)
    regime_row = _build_regime_row(
        symbol="AAPL",
        asset_class="stock",
        candle_time=candle_time,
        label="risk_on",
        regime_score="0.75",
        trend_strength="0.74",
        participation="0.61",
        macro_context="0.68",
        stability="0.70",
    )
    regime_row = RegimeDetectionRecord(
        symbol=regime_row.symbol,
        asset_class=regime_row.asset_class,
        timeframe=regime_row.timeframe,
        candle_time=regime_row.candle_time,
        source_label=regime_row.source_label,
        technical_scoring_version=regime_row.technical_scoring_version,
        sentiment_scoring_version=regime_row.sentiment_scoring_version,
        detection_version="future_version",
        regime_label=regime_row.regime_label,
        regime_score=regime_row.regime_score,
        component_scores=regime_row.component_scores,
        inputs=regime_row.inputs,
    )

    try:
        service.compose_universe(
            [_build_technical_row(symbol="AAPL", asset_class="stock", candle_time=candle_time, score="0.74", trend="0.76", momentum="0.73", volume="0.64", structure="0.70")],
            [_build_sentiment_row(symbol="AAPL", asset_class="stock", candle_time=candle_time, score="0.66", news="0.64", narrative="0.68", sector="0.67", macro="0.65")],
            [regime_row],
        )
    except ValueError as exc:
        assert str(exc) == "unsupported regime detection_version: future_version"
    else:
        raise AssertionError("expected ValueError for unsupported regime detection version")


def test_summarize_reports_selected_counts() -> None:
    service = UniverseComposerService()
    candle_time = datetime(2026, 1, 20, 18, tzinfo=UTC)

    summary = service.summarize(
        [
            _build_technical_row(symbol="AAPL", asset_class="stock", candle_time=candle_time, score="0.78", trend="0.80", momentum="0.75", volume="0.68", structure="0.74"),
            _build_technical_row(symbol="BTC/USD", asset_class="crypto", candle_time=candle_time, score="0.86", trend="0.89", momentum="0.84", volume="0.76", structure="0.82"),
        ],
        [
            _build_sentiment_row(symbol="AAPL", asset_class="stock", candle_time=candle_time, score="0.71", news="0.69", narrative="0.73", sector="0.70", macro="0.72"),
            _build_sentiment_row(symbol="BTC/USD", asset_class="crypto", candle_time=candle_time, score="0.66", news="0.63", narrative="0.68", sector="0.64", macro="0.69"),
        ],
        [
            _build_regime_row(symbol="AAPL", asset_class="stock", candle_time=candle_time, label="risk_on", regime_score="0.76", trend_strength="0.79", participation="0.64", macro_context="0.70", stability="0.73"),
            _build_regime_row(symbol="BTC/USD", asset_class="crypto", candle_time=candle_time, label="risk_on", regime_score="0.82", trend_strength="0.85", participation="0.71", macro_context="0.67", stability="0.76"),
        ],
        max_candidates=1,
    )

    assert summary.rows_technical_input == 2
    assert summary.rows_sentiment_input == 2
    assert summary.rows_regime_input == 2
    assert summary.rows_eligible == 2
    assert summary.rows_composed == 2
    assert summary.rows_selected == 1
    assert summary.composition_version == "11g_v1"
    assert summary.technical_scoring_version == "11d_v1"
    assert summary.sentiment_scoring_version == "11e_v1"
    assert summary.regime_detection_version == "11f_v1"
