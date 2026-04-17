from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[3]
ENV_FILE = ROOT_DIR / ".env"


class Settings(BaseSettings):
    app_name: str = Field(
        default="AI-Trader-v1",
        validation_alias=AliasChoices("APP_NAME", "app_name"),
    )
    environment: str = Field(
        default="local",
        validation_alias=AliasChoices("ENVIRONMENT", "APP_ENV", "environment"),
    )
    app_timezone: str = Field(
        default="America/New_York",
        validation_alias=AliasChoices("APP_TIMEZONE", "TIMEZONE", "app_timezone"),
    )

    postgres_host: str = Field(
        default="localhost",
        validation_alias=AliasChoices("POSTGRES_HOST", "postgres_host"),
    )
    postgres_port: int = Field(
        default=5432,
        validation_alias=AliasChoices("POSTGRES_PORT", "postgres_port"),
    )
    postgres_db: str = Field(
        default="ai_trader_v1",
        validation_alias=AliasChoices("POSTGRES_DB", "postgres_db"),
    )
    postgres_user: str = Field(
        default="postgres",
        validation_alias=AliasChoices("POSTGRES_USER", "postgres_user"),
    )
    postgres_password: str = Field(
        default="postgres",
        validation_alias=AliasChoices("POSTGRES_PASSWORD", "postgres_password"),
    )

    redis_host: str = Field(
        default="localhost",
        validation_alias=AliasChoices("REDIS_HOST", "redis_host"),
    )
    redis_port: int = Field(
        default=6379,
        validation_alias=AliasChoices("REDIS_PORT", "redis_port"),
    )

    tradier_api_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("TRADIER_API_TOKEN", "TRADIER_TOKEN", "tradier_api_token"),
    )

    market_data_worker_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("MARKET_DATA_WORKER_ENABLED", "market_data_worker_enabled"),
    )
    market_data_fetch_delay_seconds: int = Field(
        default=20,
        validation_alias=AliasChoices("MARKET_DATA_FETCH_DELAY_SECONDS", "market_data_fetch_delay_seconds"),
    )
    market_data_crypto_symbols: str = Field(
        default="BTC/USD,ETH/USD",
        validation_alias=AliasChoices("MARKET_DATA_CRYPTO_SYMBOLS", "market_data_crypto_symbols"),
    )
    market_data_stock_symbols: str = Field(
        default="AAPL,MSFT",
        validation_alias=AliasChoices("MARKET_DATA_STOCK_SYMBOLS", "market_data_stock_symbols"),
    )
    market_data_intervals: str = Field(
        default="5m,15m,1h,4h,1d",
        validation_alias=AliasChoices("MARKET_DATA_INTERVALS", "market_data_intervals"),
    )

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    @property
    def market_data_crypto_symbols_list(self) -> tuple[str, ...]:
        return self._parse_csv(self.market_data_crypto_symbols)

    @property
    def market_data_stock_symbols_list(self) -> tuple[str, ...]:
        return self._parse_csv(self.market_data_stock_symbols)

    @property
    def market_data_intervals_list(self) -> tuple[str, ...]:
        return self._parse_csv(self.market_data_intervals)

    def _parse_csv(self, raw_value: str) -> tuple[str, ...]:
        return tuple(item.strip() for item in raw_value.split(",") if item.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
