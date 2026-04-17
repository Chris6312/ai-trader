from __future__ import annotations

from app.market_data.kraken import KrakenMarketDataAdapter
from app.market_data.tradier import TradierMarketDataAdapter
from app.models import AssetClass, CandleInterval, MarketDataProvider


def test_kraken_adapter_parses_ohlc_ticker_and_metadata() -> None:
    adapter = KrakenMarketDataAdapter()

    ohlc_payload = {
        "result": {
            "XBTUSD": [
                [1713355200, "64000.1", "64150.2", "63950.0", "64110.0", "64055.5", "12.25", 321],
            ]
        }
    }
    ticker_payload = {
        "result": {
            "XBTUSD": {
                "a": ["64120.0", "1", "1.0"],
                "b": ["64100.0", "1", "1.0"],
                "c": ["64110.0", "0.1"],
                "v": ["100.0", "250.5"],
            }
        }
    }
    asset_pair_payload = {
        "wsname": "BTC/USD",
        "tick_size": "0.1",
        "lot_decimals": 8,
        "status": "online",
    }

    candles = adapter.parse_ohlc_response("XBTUSD", CandleInterval.HOUR_1, ohlc_payload)
    quote = adapter.parse_ticker_response("XBTUSD", ticker_payload)
    metadata = adapter.parse_asset_pair_response("XBTUSD", asset_pair_payload)

    assert len(candles) == 1
    assert candles[0].provider == MarketDataProvider.KRAKEN
    assert candles[0].asset_class == AssetClass.CRYPTO
    assert candles[0].symbol == "XBT/USD"
    assert candles[0].interval == CandleInterval.HOUR_1
    assert str(candles[0].close_price) == "64110.0"
    assert quote.symbol == "XBT/USD"
    assert str(quote.mark) == "64110.0"
    assert metadata.symbol == "BTC/USD"
    assert metadata.base_currency == "BTC"
    assert metadata.quote_currency == "USD"


def test_tradier_adapter_parses_history_quote_and_metadata() -> None:
    adapter = TradierMarketDataAdapter()

    history_payload = {
        "history": {
            "day": [
                {
                    "date": "2026-04-16",
                    "open": 187.2,
                    "high": 190.0,
                    "low": 186.5,
                    "close": 189.3,
                    "volume": 1234567,
                }
            ]
        }
    }
    quote_payload = {
        "quotes": {
            "quote": {
                "symbol": "AAPL",
                "bid": 189.2,
                "ask": 189.4,
                "last": 189.3,
                "volume": 3456789,
                "type": "stock",
            }
        }
    }

    candles = adapter.parse_history_response("AAPL", CandleInterval.DAY_1, history_payload)
    quote = adapter.parse_quote_response("AAPL", quote_payload)
    metadata = adapter.build_symbol_metadata("AAPL", quote_payload["quotes"]["quote"])

    assert len(candles) == 1
    assert candles[0].provider == MarketDataProvider.TRADIER
    assert candles[0].asset_class == AssetClass.STOCK
    assert candles[0].symbol == "AAPL"
    assert str(candles[0].close_price) == "189.3"
    assert quote.symbol == "AAPL"
    assert str(quote.mark) == "189.3"
    assert metadata.provider_symbol == "AAPL"
    assert metadata.quote_currency == "USD"
    assert metadata.is_active is True
