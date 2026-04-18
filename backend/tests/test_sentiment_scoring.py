from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.services.historical.sentiment_scoring import SentimentScoringService
from app.services.historical.sentiment_scoring_schemas import SentimentInputRecord


def _build_sentiment_rows(*, symbol: str = "AAPL", asset_class: str = "stock") -> list[SentimentInputRecord]:
    start = datetime(2026, 1, 20, tzinfo=UTC)
    rows: list[SentimentInputRecord] = []
    for index in range(4):
        rows.append(
            SentimentInputRecord(
                symbol=symbol,
                asset_class=asset_class,
                timeframe="1h",
                candle_time=start + timedelta(hours=index),
                source_label="alpaca" if asset_class == "stock" else "kraken_csv",
                input_version="11e_input_v1",
                signals={
                    "news_polarity": Decimal("0.20") + Decimal(index) / Decimal("10"),
                    "narrative_strength": Decimal("0.55") + Decimal(index) / Decimal("20"),
                    "sector_tailwind": Decimal("0.60") + Decimal(index) / Decimal("20"),
                    "macro_alignment": Decimal("0.40") + Decimal(index) / Decimal("20"),
                },
            )
        )
    return rows


def test_score_latest_input_row_returns_expected_components() -> None:
    service = SentimentScoringService()
    latest = service.score_latest_input_row(_build_sentiment_rows())

    assert latest is not None
    assert latest.symbol == "AAPL"
    assert latest.scoring_version == "11e_v1"
    assert latest.component_scores["news"] == Decimal("0.75")
    assert latest.component_scores["narrative"] == Decimal("0.70")
    assert latest.component_scores["sector"] == Decimal("0.75")
    assert latest.component_scores["macro"] == Decimal("0.55")
    assert latest.sentiment_score == Decimal("0.705")


def test_score_input_rows_supports_crypto_series() -> None:
    service = SentimentScoringService()
    scored = service.score_input_rows(_build_sentiment_rows(symbol="BTC/USD", asset_class="crypto"))

    assert len(scored) == 4
    assert scored[-1].asset_class == "crypto"
    assert scored[-1].source_label == "kraken_csv"
    assert scored[-1].sentiment_score > Decimal("0.60")


def test_score_input_rows_requires_required_signal_keys() -> None:
    service = SentimentScoringService()
    rows = _build_sentiment_rows()
    row = rows[-1]
    broken = SentimentInputRecord(
        symbol=row.symbol,
        asset_class=row.asset_class,
        timeframe=row.timeframe,
        candle_time=row.candle_time,
        source_label=row.source_label,
        input_version=row.input_version,
        signals={key: value for key, value in row.signals.items() if key != "macro_alignment"},
    )
    rows[-1] = broken

    try:
        service.score_input_rows(rows)
    except ValueError as exc:
        assert str(exc) == "sentiment input row missing required keys: macro_alignment"
    else:
        raise AssertionError("expected ValueError for missing sentiment key")


def test_summarize_reports_scored_counts() -> None:
    service = SentimentScoringService()
    summary = service.summarize(_build_sentiment_rows())

    assert summary is not None
    assert summary.rows_input == 4
    assert summary.rows_scored == 4
    assert summary.scoring_version == "11e_v1"
    assert summary.input_version == "11e_input_v1"
