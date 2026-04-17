from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[3]
ENV_FILE = ROOT_DIR / ".env"


class Settings(BaseSettings):
    app_name: str = "AI-Trader-v1"
    environment: str = "local"
    app_timezone: str = "America/New_York"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "ai_trader_v1"
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"

    redis_host: str = "localhost"
    redis_port: int = 6379

    tradier_api_token: str | None = None

    market_data_worker_enabled: bool = False
    market_data_fetch_delay_seconds: int = 20
    market_data_crypto_symbols: str = "BTC/USD,ETH/USD"
    market_data_stock_symbols: str = "AAPL,MSFT"
    market_data_intervals: str = "5m,15m,1h,4h,1d"

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
