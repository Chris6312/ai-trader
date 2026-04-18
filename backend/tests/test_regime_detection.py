from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.services.historical.regime_detection import RegimeDetectionService
from app.services.historical.sentiment_scoring_schemas import SentimentScoreRecord
from app.services.historical.technical_scoring_schemas import TechnicalScoreRecord


def _build_technical_rows(*, symbol: str = "AAPL", asset_class: str = "stock") -> list[TechnicalScoreRecord]:
    start = datetime(2026, 1, 20, tzinfo=UTC)
    rows: list[TechnicalScoreRecord] = []
    for index in range(4):
        rows.append(
            TechnicalScoreRecord(
                symbol=symbol,
                asset_class=asset_class,
                timeframe="1h",
                candle_time=start + timedelta(hours=index),
                source_label="alpaca" if asset_class == "stock" else "kraken_csv",
                feature_version="11c_v1",
                scoring_version="11d_v1",
                technical_score=Decimal("0.66") + Decimal(index) / Decimal("100"),
                component_scores={
                    "trend": Decimal("0.64") + Decimal(index) / Decimal("100"),
                    "momentum": Decimal("0.62") + Decimal(index) / Decimal("100"),
                    "volume": Decimal("0.58") + Decimal(index) / Decimal("100"),
                    "structure": Decimal("0.68") + Decimal(index) / Decimal("100"),
                },
                inputs={},
            )
        )
    return rows


def _build_sentiment_rows(*, symbol: str = "AAPL", asset_class: str = "stock") -> list[SentimentScoreRecord]:
    start = datetime(2026, 1, 20, tzinfo=UTC)
    rows: list[SentimentScoreRecord] = []
    for index in range(4):
        rows.append(
            SentimentScoreRecord(
                symbol=symbol,
                asset_class=asset_class,
                timeframe="1h",
                candle_time=start + timedelta(hours=index),
                source_label="alpaca" if asset_class == "stock" else "kraken_csv",
                input_version="11e_input_v1",
                scoring_version="11e_v1",
                sentiment_score=Decimal("0.61") + Decimal(index) / Decimal("100"),
                component_scores={
                    "news": Decimal("0.57") + Decimal(index) / Decimal("100"),
                    "narrative": Decimal("0.60") + Decimal(index) / Decimal("100"),
                    "sector": Decimal("0.63") + Decimal(index) / Decimal("100"),
                    "macro": Decimal("0.59") + Decimal(index) / Decimal("100"),
                },
                inputs={},
            )
        )
    return rows


def test_detect_latest_regime_returns_expected_components() -> None:
    service = RegimeDetectionService()
    latest = service.detect_latest_regime(_build_technical_rows(), _build_sentiment_rows())

    assert latest is not None
    assert latest.symbol == "AAPL"
    assert latest.detection_version == "11f_v1"
    assert latest.component_scores["trend_strength"] == Decimal("0.6766666666666666666666666667")
    assert latest.component_scores["participation"] == Decimal("0.62")
    assert latest.component_scores["macro_context"] == Decimal("0.6266666666666666666666666667")
    assert latest.component_scores["stability"] == Decimal("0.6658333333333333333333333333")
    assert latest.regime_score == Decimal("0.6610")
    assert latest.regime_label == "neutral"


def test_detect_regimes_supports_crypto_series() -> None:
    service = RegimeDetectionService()
    detected = service.detect_regimes(
        _build_technical_rows(symbol="BTC/USD", asset_class="crypto"),
        _build_sentiment_rows(symbol="BTC/USD", asset_class="crypto"),
    )

    assert len(detected) == 4
    assert detected[-1].asset_class == "crypto"
    assert detected[-1].source_label == "kraken_csv"
    assert detected[-1].regime_score > Decimal("0.60")


def test_detect_regimes_requires_matching_symbol() -> None:
    service = RegimeDetectionService()

    try:
        service.detect_regimes(_build_technical_rows(symbol="AAPL"), _build_sentiment_rows(symbol="MSFT"))
    except ValueError as exc:
        assert str(exc) == "regime technical and sentiment series must reference the same symbol"
    else:
        raise AssertionError("expected ValueError for mismatched symbol")


def test_detect_regimes_requires_required_sentiment_components() -> None:
    service = RegimeDetectionService()
    rows = _build_sentiment_rows()
    row = rows[-1]
    rows[-1] = SentimentScoreRecord(
        symbol=row.symbol,
        asset_class=row.asset_class,
        timeframe=row.timeframe,
        candle_time=row.candle_time,
        source_label=row.source_label,
        input_version=row.input_version,
        scoring_version=row.scoring_version,
        sentiment_score=row.sentiment_score,
        component_scores={key: value for key, value in row.component_scores.items() if key != "macro"},
        inputs=row.inputs,
    )

    try:
        service.detect_regimes(_build_technical_rows(), rows)
    except ValueError as exc:
        assert str(exc) == "sentiment score row missing required components: macro"
    else:
        raise AssertionError("expected ValueError for missing sentiment component")


def test_summarize_reports_intersection_counts() -> None:
    service = RegimeDetectionService()
    summary = service.summarize(_build_technical_rows(), _build_sentiment_rows()[:-1])

    assert summary is not None
    assert summary.rows_technical_input == 4
    assert summary.rows_sentiment_input == 3
    assert summary.rows_classified == 3
    assert summary.detection_version == "11f_v1"
    assert summary.technical_scoring_version == "11d_v1"
    assert summary.sentiment_scoring_version == "11e_v1"
