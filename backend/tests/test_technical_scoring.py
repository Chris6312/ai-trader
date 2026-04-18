from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.services.historical.feature_schemas import HistoricalFeatureRecord
from app.services.historical.technical_scoring import TechnicalScoringService


def _build_feature_rows(*, symbol: str = "AAPL", asset_class: str = "stock") -> list[HistoricalFeatureRecord]:
    start = datetime(2026, 1, 20, tzinfo=UTC)
    rows: list[HistoricalFeatureRecord] = []
    for index in range(4):
        rows.append(
            HistoricalFeatureRecord(
                symbol=symbol,
                asset_class=asset_class,
                timeframe="1h",
                candle_time=start + timedelta(hours=index),
                source_label="alpaca" if asset_class == "stock" else "kraken_csv",
                feature_version="11c_v1",
                values={
                    "body_pct": Decimal("0.006") + Decimal(index) / Decimal("1000"),
                    "close_vs_sma_5": Decimal("0.010") + Decimal(index) / Decimal("1000"),
                    "close_vs_sma_20": Decimal("0.020") + Decimal(index) / Decimal("1000"),
                    "return_3": Decimal("0.012") + Decimal(index) / Decimal("1000"),
                    "return_5": Decimal("0.016") + Decimal(index) / Decimal("1000"),
                    "return_10": Decimal("0.022") + Decimal(index) / Decimal("1000"),
                    "range_position_20": Decimal("0.78") + Decimal(index) / Decimal("100"),
                    "sma_5_vs_sma_20": Decimal("0.014") + Decimal(index) / Decimal("1000"),
                    "volume_ratio_5": Decimal("1.20") + Decimal(index) / Decimal("10"),
                    "volume_ratio_10": Decimal("1.10") + Decimal(index) / Decimal("10"),
                },
            )
        )
    return rows


def test_score_latest_feature_row_returns_expected_components() -> None:
    service = TechnicalScoringService()
    latest = service.score_latest_feature_row(_build_feature_rows())

    assert latest is not None
    assert latest.symbol == "AAPL"
    assert latest.scoring_version == "11d_v1"
    assert latest.component_scores["trend"] == Decimal("0.6673611111111111111111111107")
    assert latest.component_scores["volume"] == Decimal("0.65")
    assert latest.component_scores["structure"] == Decimal("0.716346153846153846153846154")
    assert latest.technical_score == Decimal("0.6790838675213675213675213674")


def test_score_feature_rows_supports_crypto_series() -> None:
    service = TechnicalScoringService()
    scored = service.score_feature_rows(_build_feature_rows(symbol="BTC/USD", asset_class="crypto"))

    assert len(scored) == 4
    assert scored[-1].asset_class == "crypto"
    assert scored[-1].source_label == "kraken_csv"
    assert scored[-1].technical_score > Decimal("0.60")


def test_score_feature_rows_requires_required_feature_keys() -> None:
    service = TechnicalScoringService()
    rows = _build_feature_rows()
    row = rows[-1]
    broken = HistoricalFeatureRecord(
        symbol=row.symbol,
        asset_class=row.asset_class,
        timeframe=row.timeframe,
        candle_time=row.candle_time,
        source_label=row.source_label,
        feature_version=row.feature_version,
        values={key: value for key, value in row.values.items() if key != "body_pct"},
    )
    rows[-1] = broken

    try:
        service.score_feature_rows(rows)
    except ValueError as exc:
        assert str(exc) == "feature row missing required keys: body_pct"
    else:
        raise AssertionError("expected ValueError for missing feature key")


def test_summarize_reports_scored_counts() -> None:
    service = TechnicalScoringService()
    summary = service.summarize(_build_feature_rows())

    assert summary is not None
    assert summary.rows_input == 4
    assert summary.rows_scored == 4
    assert summary.scoring_version == "11d_v1"
    assert summary.feature_version == "11c_v1"
