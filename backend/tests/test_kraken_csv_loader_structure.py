from __future__ import annotations

from pathlib import Path

from app.services.historical.kraken_csv_loader import KrakenCsvLoader


def test_kraken_csv_loader_parses_epoch_rows(tmp_path: Path) -> None:
    path = tmp_path / "XBTUSD_60.csv"
    path.write_text(
        "1704067200,42000,42500,41800,42300,12.5\n"
        "1704070800,42300,42600,42200,42550,10.1\n",
        encoding="utf-8",
    )

    loader = KrakenCsvLoader()
    rows = loader.load_file(path=path, timeframe="1h")

    assert len(rows) == 2
    assert rows[0].symbol == "BTC/USD"
    assert rows[0].asset_class == "crypto"
    assert rows[0].timeframe == "1h"
    assert str(rows[0].open) == "42000"
    assert str(rows[0].volume) == "12.5"
    assert rows[0].source_label == "kraken_csv"
    assert rows[0].retention_bucket == "intraday_medium"


def test_kraken_csv_loader_discovers_matching_files(tmp_path: Path) -> None:
    (tmp_path / "XBTUSD_60.csv").write_text("1704067200,1,2,0.5,1.5,10\n", encoding="utf-8")
    (tmp_path / "ETHUSD_60.csv").write_text("1704067200,1,2,0.5,1.5,10\n", encoding="utf-8")
    (tmp_path / "SOLUSD_240.csv").write_text("1704067200,1,2,0.5,1.5,10\n", encoding="utf-8")

    loader = KrakenCsvLoader()
    files = loader.discover_files(directory=tmp_path, timeframe="1h")

    assert [file.name for file in files] == ["ETHUSD_60.csv", "XBTUSD_60.csv"]


def test_kraken_csv_loader_load_directory_sorts_output(tmp_path: Path) -> None:
    (tmp_path / "ETHUSD_15.csv").write_text("1704068100,1,2,0.5,1.5,10\n", encoding="utf-8")
    (tmp_path / "XBTUSD_15.csv").write_text("1704067200,3,4,2.5,3.5,11\n", encoding="utf-8")

    loader = KrakenCsvLoader()
    rows = loader.load_directory(directory=tmp_path, timeframe="15m")

    assert len(rows) == 2
    assert [(row.symbol, row.timeframe) for row in rows] == [
        ("BTC/USD", "15m"),
        ("ETH/USD", "15m"),
    ]
