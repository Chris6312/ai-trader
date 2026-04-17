from pathlib import Path

from app.core.config import Settings


def test_settings_accept_existing_env_example_names(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "APP_NAME=AI-Trader-v1",
                "APP_ENV=dev",
                "TIMEZONE=America/New_York",
                "POSTGRES_HOST=db.local",
                "POSTGRES_PORT=5433",
                "POSTGRES_DB=ai_trader",
                "POSTGRES_USER=test_user",
                "POSTGRES_PASSWORD=test_password",
                "REDIS_HOST=redis.local",
                "REDIS_PORT=6380",
                "TRADIER_TOKEN=test-token",
                "MARKET_DATA_WORKER_ENABLED=true",
                "MARKET_DATA_STOCK_SYMBOLS=AAPL,MSFT",
                "MARKET_DATA_CRYPTO_SYMBOLS=BTC/USD,ETH/USD",
                "MARKET_DATA_INTERVALS=5m,1d",
            ]
        ),
        encoding="utf-8",
    )

    settings = Settings(_env_file=str(env_file))

    assert settings.app_name == "AI-Trader-v1"
    assert settings.environment == "dev"
    assert settings.app_timezone == "America/New_York"
    assert settings.postgres_host == "db.local"
    assert settings.postgres_port == 5433
    assert settings.redis_host == "redis.local"
    assert settings.tradier_api_token == "test-token"
    assert settings.market_data_worker_enabled is True
    assert settings.market_data_stock_symbols_list == ("AAPL", "MSFT")
    assert settings.market_data_crypto_symbols_list == ("BTC/USD", "ETH/USD")
    assert settings.market_data_intervals_list == ("5m", "1d")
